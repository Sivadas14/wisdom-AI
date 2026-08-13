import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import os
import asyncio
from pathlib import Path
from fire import Fire
from typing import List
import aiofiles

from src.settings import get_llm
from src.chunking import extract_pdf_text, extract_docx_text
from src.db import get_background_session, SourceDocument, DocumentChunk, DocumentStatus
from src.settings import get_supabase_client, get_settings


async def process_single_file(fp: str, semaphore: asyncio.Semaphore):
    """Process a single file with semaphore for concurrency control"""
    async with semaphore:
        try:
            tu.logger.info(f">>> Loading file: {fp}")
            is_pdf = fp.endswith(".pdf")
            is_docx = fp.endswith(".docx")
            if not is_pdf and not is_docx:
                tu.logger.warning(f"Skipping unsupported file type: {fp}")
                return {"status": "skipped", "file": fp, "reason": "unsupported type"}

            # Get file info
            filename = os.path.basename(fp)
            file_size = os.path.getsize(fp)

            async with aiofiles.open(fp, "rb") as f:
                content = await f.read()
                if is_pdf:
                    chunks = await extract_pdf_text(content)
                elif is_docx:
                    chunks = await extract_docx_text(content)
                else:
                    raise ValueError(f"Unsupported file type: {fp}")

            tu.logger.info(f"Extracted {len(chunks)} chunks from {filename}")
            if not chunks:
                tu.logger.warning(f"No chunks found for file: {fp}")
                return {"status": "skipped", "file": fp, "reason": "no chunks"}

            # Get the embeddings
            model = get_llm("gpt-4o")
            chunk_texts = list(tu.batched([c.content for c in chunks], 15))
            embeddings = []
            for chunk_text in chunk_texts:
                embeddings.extend((await model.embedding_async(chunk_text)).embedding)
            tu.logger.info(
                f"Generated embeddings for {filename}: {len(embeddings)} chunks x {len(embeddings[0])} dimensions"
            )

            # Upload to supabase
            tu.logger.info(f"Uploading to supabase: {filename}")
            client = get_supabase_client(get_settings())
            resp = client.storage.from_("source-files").upload(
                path=filename,
                file=content,
                file_options={
                    "cache-control": "3600",
                    "upsert": "true",
                },
            )
            tu.logger.info(f"Uploaded to supabase: {resp.path}")

            # Save to database
            tu.logger.info(f"Saving to database: {filename}")
            async with get_background_session() as session:
                try:
                    # Create source document
                    source_doc = SourceDocument(
                        filename=resp.path,
                        file_size_bytes=file_size,
                        status=DocumentStatus.PROCESSING,
                        active=True,
                    )
                    session.add(source_doc)
                    await session.flush()
                    await session.refresh(source_doc)

                    # Create chunks
                    chunk_records = []
                    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                        chunk_record = DocumentChunk(
                            source_document_id=source_doc.id,
                            content=chunk.content,
                            embedding=embedding,
                            location=chunk.loc,
                            model_used=model.model_id,
                        )
                        chunk_records.append(chunk_record)
                        session.add(chunk_record)

                    # Update source document status to completed
                    source_doc.status = DocumentStatus.COMPLETED

                    await session.commit()
                    tu.logger.info(
                        f"✓ Successfully saved '{filename}' with {len(chunk_records)} chunks (ID: {source_doc.id})"
                    )
                    return {
                        "status": "success",
                        "file": fp,
                        "filename": filename,
                        "chunks": len(chunk_records),
                        "doc_id": source_doc.id,
                    }

                except Exception as e:
                    await session.rollback()
                    tu.logger.error(f"Error saving {filename} to database: {e}")
                    raise
                finally:
                    await session.close()

        except Exception as e:
            tu.logger.error(f"✗ Failed to process {fp}: {str(e)}")
            return {"status": "failed", "file": fp, "error": str(e)}


async def main(
    folder_path: str,
    max_concurrent: int = 3,
    file_pattern: str = "*.pdf",
):
    """
    Batch upload files from a folder to the database.
    
    Args:
        folder_path: Path to the folder containing files to upload
        max_concurrent: Maximum number of files to process concurrently (default: 3)
        file_pattern: File pattern to match (default: *.pdf)
    """
    tu.logger.info(f"Starting batch upload from: {folder_path}")
    tu.logger.info(f"File pattern: {file_pattern}")
    tu.logger.info(f"Max concurrent uploads: {max_concurrent}")

    # Get all matching files
    folder = Path(folder_path)
    if not folder.exists():
        raise ValueError(f"Folder does not exist: {folder_path}")

    files = list(folder.glob(file_pattern))
    if not files:
        tu.logger.warning(f"No files found matching pattern '{file_pattern}' in {folder_path}")
        return

    tu.logger.info(f"Found {len(files)} files to process")

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrent)

    # Process all files concurrently
    tasks = [process_single_file(str(fp), semaphore) for fp in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Print summary
    tu.logger.info("\n" + "=" * 80)
    tu.logger.info("BATCH UPLOAD SUMMARY")
    tu.logger.info("=" * 80)

    success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
    failed_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "failed")
    skipped_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "skipped")

    tu.logger.info(f"Total files: {len(files)}")
    tu.logger.info(f"✓ Successful: {success_count}")
    tu.logger.info(f"✗ Failed: {failed_count}")
    tu.logger.info(f"⊘ Skipped: {skipped_count}")

    if failed_count > 0:
        tu.logger.info("\nFailed files:")
        for r in results:
            if isinstance(r, dict) and r.get("status") == "failed":
                tu.logger.info(f"  - {r['file']}: {r.get('error', 'Unknown error')}")

    if skipped_count > 0:
        tu.logger.info("\nSkipped files:")
        for r in results:
            if isinstance(r, dict) and r.get("status") == "skipped":
                tu.logger.info(f"  - {r['file']}: {r.get('reason', 'Unknown reason')}")

    tu.logger.info("=" * 80)


if __name__ == "__main__":
    Fire(main)
