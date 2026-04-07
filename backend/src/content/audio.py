import tempfile
import os
import subprocess
import time
import hashlib
import json
import asyncio
from textwrap import dedent
import tiktoken
from tuneapi import tt, tu

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from supabase import Client

from src.db import (
    ContentGeneration,
    ContentType,
    Conversation,
    Message,
    SourceDocument,
    DocumentChunk,
)
from src.settings import get_llm, get_supabase_client, get_supabase_admin_client, get_settings
from src.db import get_db_session, get_background_session
# Import the optimized queries
from src.db import OptimizedQueries

from src.utils.profiler import profile_operation, get_profiler, print_profiler_summary

# Cache for meditation transcripts
_transcript_cache = {}
# Version salt to force cache refresh when logic changes
_CACHE_VERSION = "v4" 

def _get_cache_key(source_text: str, length: str = None) -> str:
    """Generate cache key for source text and length"""
    key_content = f"{source_text}_{length}_{_CACHE_VERSION}" if length else f"{source_text}_{_CACHE_VERSION}"
    return hashlib.md5(key_content.encode()).hexdigest()

def _remove_transcript_artifacts(text: str) -> str:
    """Remove common transcript artifacts that TTS shouldn't read verbatim"""
    # Punctuation names
    text = text.replace('dot dot', '').replace('dot dot dot', '').replace('dots', '')
    text = text.replace('hyphen', '').replace('dash', '').replace('minus', '')
    text = text.replace('comma', '').replace('period', '').replace('full stop', '')
    text = text.replace('exclamation', '').replace('question mark', '')
    text = text.replace('colon', '').replace('semicolon', '')
    text = text.replace('quotation', '').replace('quote', '').replace('apostrophe', '')
    text = text.replace('ellipsis', '').replace('three dots', '')
    # Transcription markers
    text = text.replace('end quote', '').replace('begin quote', '')
    text = text.replace('end parenthesis', '').replace('begin parenthesis', '')
    text = text.replace('close parenthesis', '').replace('open parenthesis', '')
    return text

async def generate_meditation_transcript_optimized(source_text: str, length: str = None) -> str:
    """Generate meditation transcript with caching and optimized prompt"""

    # Check cache first
    cache_key = _get_cache_key(source_text, length)
    if cache_key in _transcript_cache:
        tu.logger.info("Using cached transcript")
        return _transcript_cache[cache_key]
    
    model = get_llm("gpt-4o")
    
    # Parse length to approximate word count
    target_words = "400-500"
    target_duration = "3-minute"
    
    if length:
        tu.logger.info(f"Processing requested length: {length}")
        # Simple mapping from "X min" to word count
        try:
            minutes = int(str(length).split()[0])
            target_duration = f"{minutes}-minute"
            # Apply a multiplier to force the LLM to expand more
            # Asking for ~200 words per minute to actually get ~130-150
            target_words = f"{minutes * 200}-{minutes * 220}"
            tu.logger.info(f"Calculated target: {target_duration}, words: {target_words} (with multiplier)")
        except Exception as e:
            tu.logger.error(f"Error parsing length '{length}': {e}")
            pass
            
    # Optimized prompt - structured for expansion with few-shot example
    transcript_prompt = dedent(
        f"""
        Create a {target_duration} meditation script ({target_words} words) based on this spiritual text:
        {source_text[:20000]}
        
        ### EXAMPLE OF EXPANSION TECHNIQUE (HOW TO REACH {target_words} WORDS):
        Source Sentence: "Focus on your breath and find peace."
        Expanded Sequence: "Now, gently shift your entire awareness to the rhythm of your breath. [pause] Feel the cool air as it touches the tip of your nose, entering slowly, filling your lungs with a soft, golden light. [breathing] Notice how your chest rises, like a gentle wave on a calm ocean, and how it falls, releasing any weight you've been carrying. With every inhale, you are breathing in pure, mountain air. With every exhale, you are letting go of the world outside. [pause] Settle into this quiet space within you... the space where peace is not a goal, but your natural state. [pause]"
        
        ### YOUR TASK:
        1. STRUCTURE:
           - Introduction & Settling In (20%): Set the scene, prepare the body.
           - Deep Visualization/Focus (60%): Expand every concept in the source text into sensory details (sights, sounds, feelings) like the example above.
           - Integration & Closing (20%): Bring awareness back slowly.
        
        2. CRITICAL REQUIREMENTS:
           - TARGET LENGTH: You MUST reach at least {target_words} words. 
           - TECHNIQUE: Use the expansion technique shown in the example. Do not summarize. Elaborate.
           - TONE: Calm, soothing, repetitive, and peaceful.
           - FORMAT: Include [pause] and [breathing] tags frequently.
        
        Generate only the meditation script.
        """
    )

    # Use a more efficient thread setup
    thread = tt.Thread(
        tt.system("Create peaceful meditation scripts."),
        id="meditation_transcript_optimized"
    )

    # Cache Version
    _CACHE_VERSION = "v4"

    # For long durations (>= 10 min), use a multi-step generation to ensure length
    if length and int(str(length).split()[0]) >= 10:
        minutes = int(str(length).split()[0])
        # Determine number of phases: 10m=2, 15m=3, 20m=4
        num_phases = max(2, (minutes + 4) // 5) 
        tu.logger.info(f"Triggering {num_phases}-phase generation for {minutes} min")
        
        all_phases = []
        current_context = ""
        
        for i in range(num_phases):
            phase_num = i + 1
            is_first = (phase_num == 1)
            is_last = (phase_num == num_phases)
            
            if is_first:
                prompt = f"{transcript_prompt}\n\nTASK: Generate PHASE {phase_num} of {num_phases} (Introduction and beginning of the meditation). Aim for {int(minutes * 70)} words. Stop mid-meditation."
            elif is_last:
                prompt = f"Previous content was good. Now continue exactly where you left off. Generate Phase {phase_num} of {num_phases} (FINAL PHASE including the conclusion). Aim for ANOTHER {int(minutes * 70)} words. Bring the experience to a complete close."
            else:
                prompt = f"Good progress. Now continue exactly where you left off. Generate Phase {phase_num} of {num_phases} (Continuing the deep meditation body). Aim for ANOTHER {int(minutes * 70)} words. Be expansive and detailed."

            if not is_first:
                thread.append(tt.Message(all_phases[-1], "assistant"))
            
            thread.append(tt.Message(prompt, "user"))
            response = await model.chat_async(thread, max_tokens=2500)
            phase_content = response.content if hasattr(response, 'content') else str(response)
            all_phases.append(phase_content)
            tu.logger.info(f"Phase {phase_num} complete: {len(phase_content.split())} words")

        response_content = "\n\n".join(all_phases)
        tu.logger.info(f"Total multi-step words: {len(response_content.split())}")
    else:
        # Standard one-step generation for shorter durations
        tu.logger.info(f"Using single-step generation for {length or 'default'} length")
        thread.append(tt.Message(transcript_prompt, "user"))
        response = await model.chat_async(thread, max_tokens=2500)
        response_content = response.content if hasattr(response, 'content') else str(response)
        tu.logger.info(f"Single-step words: {len(response_content.split())}")
    
    # Cache the result
    _transcript_cache[cache_key] = response_content
    
    return response_content

MAX_CHARS = 4000  # OpenAI TTS API limit is 4096 chars per request; 4000 gives safe headroom

async def generate_audio_from_transcript_optimized(transcript: str) -> bytes:
    """Generate audio with optimized TTS settings and chunking for long transcripts.

    Splits the transcript into <=MAX_CHARS chunks and concatenates the resulting
    audio. The previous version made a redundant full-transcript TTS call first
    (result was never used) — that wasted call has been removed.
    """

    model = get_llm("gpt-4o")

    # Clean transcript for TTS
    optimized_transcript = transcript.replace('[pause]', '...').replace('[breathing]', '...')
    optimized_transcript = _remove_transcript_artifacts(optimized_transcript)

    # Split into chunks that fit within the TTS API character limit
    chunks = []
    text = optimized_transcript
    while text:
        if len(text) <= MAX_CHARS:
            chunks.append(text)
            break
        split_idx = text.rfind('\n', 0, MAX_CHARS)
        if split_idx == -1:
            split_idx = text.rfind('. ', 0, MAX_CHARS)
        if split_idx == -1:
            split_idx = MAX_CHARS
        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()

    tu.logger.info(f"Generating {len(chunks)} audio chunk(s) for meditation...")
    audio_chunks = []
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
        audio_chunk = await model.text_to_speech_async(
            prompt=chunk,
            voice="shimmer",
            model="gpt-4o-mini-tts",
            instructions="Speak in a calm, soothing voice with natural pacing. Maintain consistent tone.",
        )
        audio_chunks.append(audio_chunk)

    return await _concatenate_audio_chunks(audio_chunks)

async def _concatenate_audio_chunks(audio_chunks: list[bytes]) -> bytes:
    """Concatenate audio chunks using FFmpeg"""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            chunk_paths = []
            for i, chunk_data in enumerate(audio_chunks):
                chunk_path = os.path.join(tmpdir, f"chunk_{i}.wav")
                with open(chunk_path, "wb") as f:
                    f.write(chunk_data)
                chunk_paths.append(chunk_path)
            
            concat_list_path = os.path.join(tmpdir, "concat_list.txt")
            with open(concat_list_path, "w") as f:
                for cp in chunk_paths:
                    clean_path = cp.replace('\\', '/')
                    f.write(f"file '{clean_path}'\n")
            
            output_path = os.path.join(tmpdir, "output.wav")
            subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", "-y", output_path], check=True, capture_output=True)
            with open(output_path, "rb") as f: return f.read()
    except Exception as e:
        tu.logger.error(f"FFmpeg concat failed: {e}")
        return b"".join(audio_chunks)

async def compress_audio_to_mp3_optimized(audio_bytes: bytes) -> bytes:
    """Compress audio with optimized FFmpeg settings"""
    
    # Use in-memory processing where possible
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as input_file:
        input_file.write(audio_bytes)
        input_path = input_file.name

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as output_file:
        output_path = output_file.name

    try:
        # Optimized FFmpeg command for speed
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-c:a", "libmp3lame",
            "-b:a", "96k",  # Lower bitrate for faster encoding
            "-preset", "ultrafast",  # Fastest encoding
            "-y",  # Overwrite output
            output_path
        ]
        
        # Add hardware acceleration if available
        try:
            subprocess.run(["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc2", "-t", "1", "-f", "null", "-"], capture_output=True)
            cmd.insert(1, "-hwaccel")
            cmd.insert(2, "auto")
        except:
            pass
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        
        with open(output_path, "rb") as f:
            compressed_audio = f.read()
        
        return compressed_audio
        
    finally:
        # Clean up temporary files
        for temp_path in [input_path, output_path]:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                tu.logger.warning(f"Failed to cleanup {temp_path}: {e}")

async def generate_audio_sync_optimized(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
    spb_client: Client,
    content_id: str,
    length: str = None  # Add length parameter
) -> tuple[str, str]:
    """Generate audio content with maximum parallelization"""
    
    request_id = f"audio_{content_id}_{int(time.time())}"
    
    # Step 1: Load conversation first (sequential)
    async with profile_operation("conversation_load", request_id) as op:
        conversation_result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conversation_result.scalar_one_or_none()
        if not conversation:
            raise ValueError(f"Conversation with id {conversation_id} not found")
        op.finish()
    
    # Step 2: Generate source content (sequential to avoid session conflicts)
    async with profile_operation("source_content_generation") as op:
        source_content = await collect_source_content_optimized(session, conversation_id)
        op.finish(content_length=len(source_content))
    
    # Step 3: Generate transcript first, then audio
    async with profile_operation("transcript_generation") as op:
        transcript = await generate_meditation_transcript_optimized(source_content, length)
        op.finish(transcript_length=len(transcript))
    
    # Step 4: Generate audio from transcript
    async with profile_operation("audio_generation") as op:
        audio_bytes = await generate_audio_from_transcript_optimized(transcript)
        op.finish(audio_size_bytes=len(audio_bytes))
    
    # Step 5: Compress audio first, then upload
    async with profile_operation("audio_compression") as op:
        compressed_audio = await compress_audio_to_mp3_optimized(audio_bytes)
        op.finish(compressed_size_bytes=len(compressed_audio))
    
    # Step 6: Upload compressed audio
    async with profile_operation("audio_upload") as op:
        content_path = await _upload_audio_optimized(compressed_audio, content_id, spb_client)
        op.finish(upload_path=content_path)
    
    print_profiler_summary()
    return content_path, transcript

async def _upload_audio_optimized(audio_bytes: bytes, content_id: str, spb_client: Client) -> str:
    """Upload audio with optimized settings"""
    content_path = f"meditation-audio/{content_id}.mp3"
    
    # Use chunked upload for large files
    chunk_size = 1024 * 1024  # 1MB chunks
    if len(audio_bytes) > chunk_size:
        # For large files, use chunked upload
        spb_client.storage.from_("generations").upload(
            content_path,
            audio_bytes,
            {"content-type": "audio/mpeg"}
        )
    else:
        # For smaller files, direct upload
        spb_client.storage.from_("generations").upload(
            content_path,
            audio_bytes,
            {"content-type": "audio/mpeg"}
        )
    
    return content_path

async def generate_audio_content(
    content_id: str,
    conversation_id: str,
    message_id: str,
    length: str = None,  # Add length parameter
) -> None:
    """Background task to generate audio content and update the database record"""

    tu.logger.info(f"Starting background audio generation for content {content_id}")
    spb_client = get_supabase_admin_client(get_settings())

    async with get_background_session() as session:
        try:
            # Generate the audio content
            content_path, transcript = await generate_audio_sync_optimized(
                session=session,
                conversation_id=conversation_id,
                message_id=message_id,
                spb_client=spb_client,
                content_id=content_id,
                length=length,
            )

            # Update the ContentGeneration record with the results
            query = select(ContentGeneration).where(ContentGeneration.id == content_id)
            result = await session.execute(query)
            content_generation = result.scalar_one_or_none()

            if content_generation:
                content_generation.content_path = content_path
                content_generation.transcript = transcript
                # Set duration based on the prompt specification
                duration = 180  # Default 3 minutes
                if length:
                    try:
                        duration = int(str(length).split()[0]) * 60
                    except:
                        pass
                content_generation.duration_seconds = duration
                await session.commit()
                tu.logger.info(
                    f"Successfully completed audio generation for content {content_id} (duration: {duration}s)"
                )
            else:
                tu.logger.error(f"ContentGeneration record not found for id {content_id}")
                # No changes were made, but ensure session is clean
                await session.rollback()

        except Exception as e:
            tu.logger.error(
                f"Error in background audio generation for content {content_id}: {e}"
            )
            # Session will be automatically rolled back by the context manager
            raise


async def collect_source_content_optimized(
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Optimized version of collect_source_content - FIXED FOR SHARED DOCUMENTS"""
    
    # Get conversation to get user_id
    conv_query = select(Conversation).where(Conversation.id == conversation_id)
    conv_result = await session.execute(conv_query)
    conversation = conv_result.scalar_one_or_none()
    
    if not conversation:
        raise ValueError("Conversation not found")
    
    # Get random chunks without user filtering since documents are shared
    query = (
        select(DocumentChunk)
        .join(SourceDocument)
        .options(selectinload(DocumentChunk.source_document))
        .where(SourceDocument.active == True)
        .order_by(func.random())
        .limit(10)
    )
    result = await session.execute(query)
    chunks = result.scalars().all()
    
    # Process chunks with null checks
    content_parts = []
    total_tokens = 0
    max_tokens = 4000  # Limit to prevent token overflow
    
    for chunk in chunks:
        # Add null check for source_document
        doc_name = chunk.source_document.filename if chunk.source_document else "Unknown Document"
        chunk_text = f"Document: {doc_name}\nContent: {chunk.content}\n\n"
        chunk_tokens = OptimizedQueries.count_tokens_optimized(chunk_text)
        
        if total_tokens + chunk_tokens > max_tokens:
            break
            
        content_parts.append(chunk_text)
        total_tokens += chunk_tokens
    
    return "".join(content_parts)


async def collect_source_content(
    session: AsyncSession,
    conversation_id: str,
    target_tokens: int = 6000,
) -> str:
    """Collect source content from conversation citations and random chunks"""

    # Step 1: Get all messages in the conversation thread till now
    messages_query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages_result = await session.execute(messages_query)
    conversation_messages = messages_result.scalars().all()

    # Step 2: Load random chunks from all citations until we have ~6K tokens
    tkz = tiktoken.encoding_for_model("gpt-4o")
    collected_content = []
    current_tokens = 0

    # Collect all citations from the conversation with null checks
    all_citations = []
    for msg in conversation_messages:
        if msg.citations and isinstance(msg.citations, list):
            all_citations.extend(msg.citations)

    if all_citations:
        # Get chunks from cited documents
        cited_filenames = [citation.name for citation in all_citations]
        chunks_query = (
            select(DocumentChunk.content, SourceDocument.filename)
            .join(SourceDocument)
            .where(
                SourceDocument.filename.in_(cited_filenames),
                SourceDocument.active == True,
            )
            .order_by(func.random())
        )
        chunks_result = await session.execute(chunks_query)
        available_chunks = chunks_result.all()

        # Add chunks until we reach the target token count
        for content, filename in available_chunks:
            chunk_tokens = len(tkz.encode(content))
            if current_tokens + chunk_tokens > target_tokens:
                break
            collected_content.append(f"From {filename}:\n{content}")
            current_tokens += chunk_tokens

        tu.logger.info(
            f"Collected {len(collected_content)} chunks from citations with {current_tokens} tokens"
        )

    # If we don't have enough content from citations, get random chunks
    if current_tokens < target_tokens:
        random_chunks_query = (
            select(DocumentChunk.content, SourceDocument.filename)
            .join(SourceDocument)
            .where(SourceDocument.active == True)
            .order_by(func.random())
        )
        random_chunks_result = await session.execute(random_chunks_query)
        random_chunks = random_chunks_result.all()

        for content, filename in random_chunks:
            chunk_tokens = len(tkz.encode(content))
            if current_tokens + chunk_tokens > target_tokens:
                break
            collected_content.append(f"From {filename}:\n{content}")
            current_tokens += chunk_tokens

        tu.logger.info(
            f"Added random chunks, total: {len(collected_content)} chunks with {current_tokens} tokens"
        )

    return "\n\n".join(collected_content)


async def generate_meditation_transcript(source_text: str) -> str:
    """Generate meditation transcript from source content"""

    model = get_llm("gpt-4o")

    transcript_prompt = dedent(
        f"""
        Based on the following spiritual and contemplative texts, create a peaceful 5-minute meditation script that captures the essence of the wisdom. The script should be:

        - Approximately 5 minutes when read aloud (about 600-750 words)
        - Written in a calm, soothing tone suitable for meditation
        - Include gentle breathing instructions and pauses
        - Focus on mindfulness, inner peace, and spiritual growth
        - Be suitable for audio narration with natural flow
        - For sound effects use tags like [breathing], [pause], [silence], [silence-n], etc.

        Source texts:
        {source_text}

        Generate only the meditation script text.
        """
    )

    # Create a thread with the prompt
    thread = tt.Thread(
        tt.system("You are a meditation script writer who creates peaceful, calming meditation scripts."),
        id="meditation_transcript"
    )
    
    # Add the user message to the thread
    thread.append(tt.Message(transcript_prompt, "user"))

    response = await model.chat_async(thread)
    
    # Fix: Handle response properly whether it's a string or object
    response_content = response.content if hasattr(response, 'content') else str(response)

    return response_content


async def generate_audio_from_transcript(transcript: str) -> bytes:
    """Generate audio from transcript using OpenAI TTS"""
    
    model = get_llm("gpt-4o")

    # Remove transcript artifacts
    cleaned_transcript = _remove_transcript_artifacts(transcript)

    audio_bytes = await model.text_to_speech_async(
        prompt=cleaned_transcript,
        voice="shimmer",
                model="gpt-4o-mini-tts",

        instructions="""
        For sound effects transcript has tags like [breathing], [pause], [silence], etc.
        Please follow these instructions:
        - Speak in a calm, soothing voice
        - Pause appropriately for breathing instructions
        - Use natural pacing for meditation
        - Maintain consistent volume and tone
        """,
    )
    
    return audio_bytes


async def compress_audio_to_mp3(audio_bytes: bytes) -> bytes:
    """Compress audio bytes to MP3 format using FFmpeg"""
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as input_file:
        input_file.write(audio_bytes)
        input_path = input_file.name

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as output_file:
        output_path = output_file.name

    try:
        # Use FFmpeg to convert to MP3
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            "-y",  # Overwrite output
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Read the compressed audio
        with open(output_path, "rb") as f:
            compressed_audio = f.read()
        
        return compressed_audio
        
    finally:
        # Clean up temporary files
        for temp_path in [input_path, output_path]:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                tu.logger.warning(f"Failed to cleanup {temp_path}: {e}")
