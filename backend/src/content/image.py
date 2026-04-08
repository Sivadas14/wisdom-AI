import uuid
from io import BytesIO
import random
from textwrap import dedent
import json

from supabase import Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os
import logging
from pydantic import ValidationError
from openai import OpenAI

# Import tuneapi components correctly for version 8.0.18
import tuneapi

from src.db import (
    ContentGeneration,
    ContentType,
    Conversation,
    Message,
    MessageRole,
    SourceDocument,
    DocumentChunk,
    RamanaImage,
)
from src.settings import get_llm, get_supabase_client, get_supabase_admin_client, get_settings
from src.db import get_db_session, get_background_session
from src.wire import ContemplationCardContent

# Set up logger
logger = logging.getLogger(__name__)

CONTEMPLATION_PROMPTS = [
    "Arunachala hill at golden sunrise, soft mist rising, warm ochre light, devotional atmosphere",
    "Interior of Sri Ramanasramam hall, oil lamp flame, worn stone floor, profound stillness",
    "Arunachala at dusk, deep violet sky, single bright star, timeless silence",
    "Ancient banyan tree at Tiruvannamalai, roots spreading, soft dawn light, sacred atmosphere",
    "Meditation cave on Arunachala hillside, simple oil lamp, stone walls, serene solitude",
    "Arunachala reflected in the still waters of the ashram tank at dawn",
    "Ramana's simple wooden couch in the Old Hall, golden afternoon light, sacred quietude",
    "Pradakshina path around Arunachala, bare feet on red earth, pilgrims at sunrise",
    "Oil lamp and incense before a simple altar, soft diffused light, devotional stillness",
    "Arunachala peak emerging from morning clouds, sacred summit, luminous sky",
    "Ancient gopuram of Arunachaleswarar temple at dawn, bells, sacred mist",
    "A single deepam flame on Arunachala summit against a vast starlit sky",
    "Peaceful ashram courtyard, a lone seeker seated in meditation under a large tree",
    "The heart of inquiry — a still pool reflecting boundless sky, symbol of pure awareness",
    "Sunrise over Tiruvannamalai plains, Arunachala casting long warm shadows, sacred hush",
    "A small reading lamp illuminating a worn copy of Talks with Sri Ramana Maharshi",
    "Silence rendered as light — warm golden glow dissolving into open space",
    "Arunachala at full moon, silver light bathing red hillside, absolute stillness",
    "Stone path winding up the holy hill, footprints, solitude, turning inward",
    "Early morning meditation beside the ashram well, soft mist, birds, profound peace",
]


# ------------------------------------------------------------
# Background task and main functions
# ------------------------------------------------------------


async def generate_image_content(
    content_id: str,
    conversation_id: str,
    message_id: str,
) -> None:
    """Background task to generate image content and update the database record"""

    spb_client = get_supabase_admin_client(get_settings())

    async with get_background_session() as session:
        try:
            logger.info(f"Starting background image generation for content {content_id}")

            # Generate the image content
            content_path, cc_text = await generate_contemplation_card_sync(
                session=session,
                conversation_id=conversation_id,
                message_id=message_id,
                spb_client=spb_client,
                content_id=content_id,
            )

            # Update the ContentGeneration record with the results
            query = select(ContentGeneration).where(ContentGeneration.id == content_id)
            result = await session.execute(query)
            content_generation = result.scalar_one_or_none()

            if content_generation:
                content_generation.content_path = content_path
                content_generation.cc_text = cc_text
                await session.commit()
                logger.info(
                    f"Successfully completed image generation for content {content_id}"
                )
            else:
                logger.error(f"ContentGeneration record not found for id {content_id}")
                # No changes were made, but ensure session is clean
                await session.rollback()

        except Exception as e:
            logger.error(
                f"Error in background image generation for content {content_id}: {e}"
            )
            # Session will be automatically rolled back by the context manager
            raise


async def generate_contemplation_card_sync(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
    spb_client: Client,
    content_id: str,
) -> tuple[str, str]:
    """Generate contemplation card synchronously and return content_path and cc_text"""

    # IMAGE PROMPT: generated from the user's question topic (fine to be creative)
    user_question = await _get_last_user_message(session, conversation_id)
    if user_question and len(user_question) > 10:
        try:
            prompt = await _generate_image_prompt_from_question(user_question)
            logger.info(f"Generated image prompt from user question: {user_question[:50]}...")
        except Exception as e:
            logger.warning(f"Question-based image prompt failed, using fallback: {e}")
            prompt = random.choice(CONTEMPLATION_PROMPTS)
    else:
        logger.info("No valid user question found, using standard Ramana image prompts")
        prompt = random.choice(CONTEMPLATION_PROMPTS)

    # QUOTE: ALWAYS sourced from actual Ramana library chunks — never GPT fabrication.
    # _get_quote_from_citations_or_random pulls from citations on the assistant message first,
    # then conversation citations, then a random authentic Ramana chunk as last resort.
    quote = await _get_quote_from_citations_or_random(
        session, conversation_id, message_id
    )

    # Get the conversation to get the user_id
    query = select(Conversation).where(Conversation.id == conversation_id)
    result = await session.execute(query)
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError(f"Conversation with id {conversation_id} not found")

    # IMAGE: try repository first; fall back to AI generation if empty
    logger.info(
        f"Generating contemplation card for conversation {conversation_id}/{message_id}"
    )
    repo_image = await _get_random_repository_image(session, spb_client)
    if repo_image is not None:
        pil_image = repo_image
        logger.info("Using repository image for contemplation card")
    else:
        logger.info("Repository empty — falling back to AI image generation")
        pil_image = await _generate_image(prompt)

    # add caption to the image
    with_caption = add_caption_to_image(pil_image, quote)
    logger.info(f"Added caption to image: {with_caption.size}")

    # create content path
    content_path = f"contemplation-cards/{content_id}.png"

    # Convert PIL image to bytes for upload
    img_buffer = BytesIO()
    with_caption.save(img_buffer, format="PNG")
    img_bytes = img_buffer.getvalue()

    # upload to the supabase storage
    logger.info(f"Uploading image to supabase: {content_path}")
    spb_client.storage.from_("generations").upload(
        content_path,
        img_bytes,
        {"content-type": "image/png"},
    )

    logger.info(f"Successfully created image content generation: {content_id}")
    return content_path, prompt


async def generate_contemplation_card(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
    spb_client: Client,
) -> ContentGeneration:
    """Legacy function - kept for backward compatibility"""

    # Generate content ID
    content_id = str(uuid.uuid4())

    # Call the sync version
    content_path, cc_text = await generate_contemplation_card_sync(
        session=session,
        conversation_id=conversation_id,
        message_id=message_id,
        spb_client=spb_client,
        content_id=content_id,
    )

    # Get the conversation to get the user_id
    query = select(Conversation).where(Conversation.id == conversation_id)
    result = await session.execute(query)
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError(f"Conversation with id {conversation_id} not found")

    # Create ContentGeneration record
    content_generation = ContentGeneration(
        id=content_id,
        user_id=conversation.user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        content_type=ContentType.IMAGE,
        content_path=content_path,
        cc_text=cc_text,
        cc_theme="nature_sunset",
    )

    session.add(content_generation)
    await session.commit()
    await session.refresh(content_generation)

    return content_generation


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------


async def _get_quote_from_citations_or_random(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
) -> str:
    """
    Check for citations in the current message or conversation.
    If none exist, pick a random source file and generate a quote from random chunks.
    """
    model = get_llm("gpt-4o")

    # First, get the current message
    current_message_query = select(Message).where(Message.id == message_id)
    current_message_result = await session.execute(current_message_query)
    current_message = current_message_result.scalar_one_or_none()

    # Check if current message has citations
    if current_message and current_message.citations:
        logger.info(
            f"Found citations in current message: {len(current_message.citations)}"
        )
        # Get chunks from cited documents
        cited_filenames = [citation.name for citation in current_message.citations]
        chunks_query = (
            select(DocumentChunk.content, SourceDocument.filename)
            .join(SourceDocument)
            .where(
                SourceDocument.filename.in_(cited_filenames),
                SourceDocument.active == True,
            )
            .limit(5)  # Get a few chunks from cited documents
        )
        chunks_result = await session.execute(chunks_query)
        cited_chunks = chunks_result.all()

        if cited_chunks:
            chunk_texts = [
                f"From {filename}: {content}" for content, filename in cited_chunks
            ]
            source_text = "\n\n".join(chunk_texts[:3])  # Use first 3 chunks
        else:
            # Fallback to random if cited documents have no chunks
            source_text = await _get_random_chunks_text(session)
    else:
        # Check if any message in the conversation has citations
        conversation_messages_query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .options(selectinload(Message.citations))
        )
        conversation_messages_result = await session.execute(
            conversation_messages_query
        )
        conversation_messages = conversation_messages_result.scalars().all()

        # Look for any message with citations
        all_citations = []
        for msg in conversation_messages:
            if msg.citations:
                all_citations.extend(msg.citations)

        if all_citations:
            logger.info(f"Found citations in conversation: {len(all_citations)}")
            # Get chunks from any cited documents in the conversation
            cited_filenames = [citation.name for citation in all_citations]
            chunks_query = (
                select(DocumentChunk.content, SourceDocument.filename)
                .join(SourceDocument)
                .where(
                    SourceDocument.filename.in_(cited_filenames),
                    SourceDocument.active == True,
                )
                .limit(5)
            )
            chunks_result = await session.execute(chunks_query)
            cited_chunks = chunks_result.all()

            if cited_chunks:
                chunk_texts = [
                    f"From {filename}: {content}" for content, filename in cited_chunks
                ]
                source_text = "\n\n".join(chunk_texts[:3])
            else:
                source_text = await _get_random_chunks_text(session)
        else:
            logger.info("No citations found, using random source file")
            source_text = await _get_random_chunks_text(session)

    # Extract a genuine quote from the Ramana source text.
    # Crucially: we ask the LLM to EXTRACT or closely paraphrase from the provided text,
    # never to invent or draw on general knowledge.
    quote_prompt = dedent(
        f"""
    You are given passages from Sri Ramana Maharshi's authenticated teachings.
    Your task is to select and return the single most profound or meaningful sentence
    (or at most two short sentences) directly from the provided text below.

    Rules:
    - You MUST quote or very closely paraphrase the actual text provided. Do NOT invent.
    - Do NOT draw on any knowledge outside the provided passages.
    - Choose the sentence that best stands alone as a contemplative insight.
    - Return ONLY the chosen sentence(s). No attribution, no filename, no source label,
      no preamble, no explanation. Just the quote itself.

    Source passages:
    {source_text}
    """
    )

    quote_response = await model.chat_async(quote_prompt)
    quote = quote_response.strip()

    # Safety: strip any trailing attribution line (e.g. "— Talks with Sri Ramana Maharshi"
    # or "Source: ..." or "From ...") that the LLM may append despite instructions.
    import re
    quote = re.sub(r'\n?\s*[—–-]+\s*\S.*$', '', quote, flags=re.MULTILINE).strip()
    quote = re.sub(r'\n?\s*(Source|From|Ref|Reference)\s*:.*$', '', quote, flags=re.IGNORECASE | re.MULTILINE).strip()
    # Strip leading "From filename:" if the LLM echoed a chunk prefix
    quote = re.sub(r'^From [^:]+:\s*', '', quote, flags=re.IGNORECASE).strip()

    return quote


async def _get_random_chunks_text(session: AsyncSession) -> str:
    """Get random chunks from a random source document."""

    # Get a random active source document
    random_doc_query = (
        select(SourceDocument)
        .where(SourceDocument.active == True)
        .order_by(func.random())
        .limit(1)
    )
    random_doc_result = await session.execute(random_doc_query)
    random_doc = random_doc_result.scalar_one_or_none()

    if not random_doc:
        logger.warning("No active source documents found")
        return "The journey of a thousand miles begins with a single step."

    # Get random chunks from this document
    chunks_query = (
        select(DocumentChunk.content)
        .where(DocumentChunk.source_document_id == random_doc.id)
        .order_by(func.random())
        .limit(3)  # Get 3 random chunks
    )
    chunks_result = await session.execute(chunks_query)
    chunks = chunks_result.scalars().all()

    if not chunks:
        logger.warning(f"No chunks found for document {random_doc.filename}")
        return "In silence, we find the deepest truths."

    return "\n\n".join(chunks)


async def _get_last_user_message(
    session: AsyncSession, 
    conversation_id: str
) -> str | None:
    """Get the most recent user message from conversation. Returns None if not found."""
    try:
        query = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.USER
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        message = result.scalar_one_or_none()
        
        if message and message.content and len(message.content.strip()) > 0:
            return message.content.strip()
        return None
    except Exception as e:
        logger.warning(f"Failed to get last user message: {e}")
        return None


async def _generate_image_prompt_from_question(user_question: str) -> str:
    """Generate a Ramana/Arunachala-themed image prompt from the user's question topic.

    Uses the established get_llm + chat_async pattern (async, non-blocking).
    Only generates the image prompt — the quote is always sourced separately from
    authentic Ramana library chunks, never from general LLM knowledge.
    """
    model = get_llm("gpt-4o")

    prompt = dedent(f"""
    You generate concise image prompts for Ramana Maharshi contemplation cards.

    Based on this spiritual question: "{user_question}"

    Generate a single evocative image prompt (1 sentence, under 25 words) for a
    peaceful contemplation card. The imagery should be rooted in the world of
    Sri Ramana Maharshi — Arunachala hill, the ashram at Tiruvannamalai, oil lamps,
    silence, sacred stillness, Tamil sacred landscape, or the pure light of
    Self-awareness. No generic nature scenes.

    Return only the image prompt sentence. Nothing else.
    """)

    try:
        response = await model.chat_async(prompt)
        return response.strip()
    except Exception as e:
        logger.error(f"Image prompt generation failed: {e}")
        raise


async def _generate_prompt_and_quote_from_question(
    user_question: str
) -> tuple[str, str]:
    """Deprecated: use _generate_image_prompt_from_question + _get_quote_from_citations_or_random.
    Kept for backward compatibility only — do not call for new card generation."""
    image_prompt = await _generate_image_prompt_from_question(user_question)
    # Return a placeholder quote; callers should use _get_quote_from_citations_or_random
    return image_prompt, ""


async def _get_random_repository_image(
    session: AsyncSession,
    spb_client: Client,
) -> Image.Image | None:
    """Pick a random active image from the Ramana image repository.

    Downloads the image bytes from Supabase storage and returns a PIL Image.
    Returns None if the repository is empty or all images are inactive,
    signalling the caller to fall back to AI generation.
    """
    try:
        query = (
            select(RamanaImage)
            .where(RamanaImage.active == True)
            .order_by(func.random())
            .limit(1)
        )
        result = await session.execute(query)
        img_record = result.scalar_one_or_none()

        if img_record is None:
            return None

        image_bytes = spb_client.storage.from_("generations").download(img_record.storage_path)
        pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")
        logger.info(f"Loaded repository image: {img_record.filename} ({img_record.storage_path})")
        return pil_image
    except Exception as e:
        logger.warning(f"Repository image load failed, will use AI generation: {e}")
        return None


async def _generate_image(prompt: str) -> Image.Image:
    logger.info(f"Generating image for prompt: {prompt}")
    model = get_llm("gpt-4o")
    img_gen_response = await model.image_gen_async(
        prompt=prompt,
        n=1,
        size="1792x1024",
        quality="standard",
    )
    logger.info(f"Generated image: {img_gen_response.image.size}")
    pil_image = img_gen_response.image
    return pil_image


def add_caption_to_image(
    image: Image.Image,
    caption_text: str,
    font_size=102,
    padding=40,
    max_width_ratio=0.88,
):
    """
    Add a caption below a PIL image with white background.

    Args:
        image: PIL Image object
        caption_text: String for the caption (can be multi-line)
        font_size: Font size for the caption
        padding: Padding around the caption text
        max_width_ratio: Maximum width ratio for text wrapping (0.88 = 88% of image width)

    Returns:
        PIL Image with caption added below
    """

    # Get original image dimensions
    orig_width, orig_height = image.size

    # Load font — try custom first, then common system fonts, never fall back to
    # ImageFont.load_default() which is a ~10px bitmap with no size support.
    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        candidates = []
        current_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(current_dir, "DM_Serif_Text", "DMSerifText-Regular.ttf"))
        # Common system font paths (Linux/Docker)
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    f = ImageFont.truetype(path, size)
                    logger.info(f"Loaded font: {path}")
                    return f
                except Exception:
                    continue
        # Last resort: load_default with size (Pillow ≥10 supports size kwarg)
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    font = _load_font(font_size)

    # Create a temporary draw object to measure text
    temp_img = Image.new("RGB", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    # Calculate maximum text width (90% of image width)
    max_text_width = int(orig_width * max_width_ratio)

    # Wrap text to fit within the image width
    wrapped_lines = []
    words = caption_text.split()
    current_line = ""

    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        bbox = temp_draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_text_width:
            current_line = test_line
        else:
            if current_line:
                wrapped_lines.append(current_line)
                current_line = word
            else:
                # Single word is too long, add it anyway
                wrapped_lines.append(word)
                current_line = ""

    if current_line:
        wrapped_lines.append(current_line)

    # Limit to 3 lines — add ellipsis to the LAST line if truncated
    if len(wrapped_lines) > 3:
        wrapped_lines = wrapped_lines[:3]
        last_line = wrapped_lines[2]
        while True:
            test_line = last_line + "…"
            bbox = temp_draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]
            if text_width <= max_text_width:
                wrapped_lines[2] = test_line
                break
            # Remove last word and try again
            words_in_line = last_line.split()
            if len(words_in_line) <= 1:
                wrapped_lines[2] = last_line + "…"
                break
            last_line = " ".join(words_in_line[:-1])

    # Calculate text dimensions
    line_height = font_size + 20  # Add generous line spacing for readability
    total_text_height = len(wrapped_lines) * line_height

    # Calculate caption area height
    caption_height = total_text_height + (padding * 2)

    # Create new image with extended height
    new_height = orig_height + caption_height
    new_image = Image.new("RGB", (orig_width, new_height), "white")

    # Paste original image at the top
    new_image.paste(image, (0, 0))

    # Draw caption text
    draw = ImageDraw.Draw(new_image)

    # Calculate starting Y position for centered text
    text_start_y = orig_height + padding

    # Draw each line of text
    for i, line in enumerate(wrapped_lines):
        # Calculate text position (centered horizontally)
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (orig_width - text_width) // 2
        text_y = text_start_y + (i * line_height)

        # Draw the text
        draw.text((text_x, text_y), line, fill="black", font=font)

    return new_image