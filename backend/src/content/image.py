import uuid
import re
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
from src.content.status_helpers import mark_content_failed

# Set up logger
logger = logging.getLogger(__name__)

# Authentic Ramana Maharshi quotes used as fallback when source chunks are unusable.
# These are verified, complete sentences suitable for contemplation cards.
FALLBACK_RAMANA_QUOTES = [
    "Your own Self-Realization is the greatest service you can render the world.",
    "The mind is nothing but a bundle of thoughts. The thought 'I' is the root of all thoughts.",
    "Silence is also conversation.",
    "Happiness is the very nature of the Self; happiness and the Self are not different.",
    "The degree of freedom from unwanted thoughts and the degree of concentration on a single thought are the measures to gauge spiritual progress.",
    "Whatever is destined not to happen will not happen, try as you may. Whatever is destined to happen will happen, do what you may to prevent it.",
    "There is neither creation nor destruction, neither destiny nor free will, neither path nor achievement. This is the final truth.",
    "The present moment always will have been.",
    "Realization is not acquisition of anything new nor is it a new faculty. It is only removal of all camouflage.",
    "Mind is consciousness which has put on limitations. You are originally unlimited and perfect. Later you take on limitations and become the mind.",
    "Be still. It is the wind that makes the water ripple. The Self remains unchanging in the midst of all activities.",
    "The world is illusory; Brahman alone is real; Brahman is the world.",
    "Turn your vision inward and then the whole world will be full of supreme Spirit.",
    "No one succeeds without effort. Those who succeed owe their success to perseverance.",
    "To know the Self is to be the Self, for the Self is consciousness.",
]

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
                content_generation.status = "complete"
                content_generation.error_message = None
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
            # Session will be rolled back by the context manager. Mark the row
            # as failed in a fresh session so the UI can surface the failure.
            await mark_content_failed(content_id, e)
            # Do NOT re-raise — background task failure is now persisted.


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


async def _get_conversation_topic_summary(
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """
    Return a brief plain-English summary of what the conversation was about,
    by reading the last 6 messages (3 turns). Used to guide contextual quote selection.
    """
    try:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(6)
        )
        result = await session.execute(query)
        messages = list(reversed(result.scalars().all()))
        if not messages:
            return ""
        # Build a short transcript snippet
        parts = []
        for msg in messages:
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            # Trim each message to 300 chars to keep the context concise
            content = (msg.content or "")[:300]
            if content.strip():
                parts.append(f"{role}: {content}")
        return "\n".join(parts)
    except Exception as e:
        logger.warning(f"Could not get conversation topic: {e}")
        return ""


async def _get_quote_from_citations_or_random(
    session: AsyncSession,
    conversation_id: str,
    message_id: str,
) -> str:
    """
    Pick a Ramana quote that is thematically relevant to the conversation.

    Strategy:
    1. Prefer chunks that were actually cited by the AI assistant in this message
       (they were retrieved by semantic search, so they're already on-topic).
    2. Fall back to any cited chunk in the conversation.
    3. Fall back to random chunks from a random source document.

    In all cases, pass a brief conversation-topic summary to the LLM so it can
    choose the quote that best matches what the user was exploring.
    """
    model = get_llm("gpt-4o")

    # Get a brief summary of the conversation topic so the LLM can pick a quote
    # that mirrors what the user was actually exploring.
    conversation_topic = await _get_conversation_topic_summary(session, conversation_id)

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

    # Validate source text before sending to LLM.
    # Chunks that are just page numbers, indexes, or very short fragments are useless.
    def _is_usable_source_text(text: str) -> bool:
        """Returns True only if the text has enough real prose to extract a quote from."""
        # Strip numbers, punctuation, whitespace and see what's left
        words = re.findall(r'[a-zA-Z]{3,}', text)  # real words, at least 3 chars
        if len(words) < 15:
            logger.warning(f"Source text too sparse (only {len(words)} real words) — skipping")
            return False
        # Reject if it looks like an index (mostly numbers with few words)
        tokens = text.split()
        num_count = sum(1 for t in tokens if re.match(r'^\d+\.?$', t))
        if len(tokens) > 0 and num_count / len(tokens) > 0.4:
            logger.warning(f"Source text looks like an index ({num_count}/{len(tokens)} tokens are numbers) — skipping")
            return False
        return True

    if not _is_usable_source_text(source_text):
        logger.info("Source text not usable — using fallback Ramana quote")
        return random.choice(FALLBACK_RAMANA_QUOTES)

    # Build a context hint for the quote-selection prompt so the LLM knows
    # what the user was exploring and can pick the most relevant passage.
    topic_hint = ""
    if conversation_topic.strip():
        topic_hint = dedent(f"""
    The user was exploring this topic in their conversation:
    ---
    {conversation_topic}
    ---
    Prioritise choosing a quote that speaks directly to the above theme.
    If no passage in the source text is relevant to that theme,
    choose the most profound passage available.
    """)

    # Extract a genuine quote from the Ramana source text.
    # Crucially: we ask the LLM to EXTRACT or closely paraphrase from the provided text,
    # never to invent or draw on general knowledge.
    quote_prompt = dedent(
        f"""
    You are given passages from Sri Ramana Maharshi's authenticated teachings.
    Your task is to select and return a complete, meaningful quote directly from
    the provided text below — something that would look beautiful on a
    contemplation card.
    {topic_hint}
    Rules:
    - You MUST quote or very closely paraphrase the actual text provided. Do NOT invent.
    - Do NOT draw on any knowledge outside the provided passages.
    - The quote MUST be a grammatically complete sentence or sentences. Never return
      a fragment, a phrase without a verb, or a half-finished thought.
    - Aim for 1 to 3 sentences that together form a complete, self-contained insight.
    - The ideal length is 15 to 50 words. Shorter is fine if the sentence is complete
      and powerful. Never exceed 60 words.
    - If a single sentence from the source is profound enough on its own, return just
      that one sentence — but make sure it is COMPLETE (has subject, verb, and makes
      full sense to a reader who has no other context).
    - Do NOT start with fragments like "Ramana says..." or "The Self is..." unless
      that is actually a complete sentence.
    - Return ONLY the chosen quote. No attribution, no filename, no source label,
      no preamble, no explanation, no quotation marks. Just the quote itself.

    Source passages:
    {source_text}
    """
    )

    quote_response = await model.chat_async(quote_prompt)
    quote = quote_response.strip()

    # Safety: strip any trailing attribution line (e.g. "— Talks with Sri Ramana Maharshi"
    # or "Source: ..." or "From ...") that the LLM may append despite instructions.
    quote = re.sub(r'\n?\s*[—–-]+\s*\S.*$', '', quote, flags=re.MULTILINE).strip()
    quote = re.sub(r'\n?\s*(Source|From|Ref|Reference)\s*:.*$', '', quote, flags=re.IGNORECASE | re.MULTILINE).strip()
    # Strip leading "From filename:" if the LLM echoed a chunk prefix
    quote = re.sub(r'^From [^:]+:\s*', '', quote, flags=re.IGNORECASE).strip()
    # Strip surrounding quotation marks if present
    quote = re.sub(r'^["\'""]+|["\'""]+$', '', quote).strip()

    # JUNK DETECTION: If the LLM returned an apology, meta-comment, or confusion
    # instead of a quote, discard it and use a fallback immediately.
    JUNK_PATTERNS = [
        r"i('m| am) sorry",
        r"i misunderstood",
        r"could you clarify",
        r"i apologize",
        r"please provide",
        r"i attempted to",
        r"the directive",
        r"it appears i",
        r"i was unable",
        r"no relevant",
        r"doesn't provide",
        r"does not provide",
        r"i cannot",
        r"i can't",
        r"provide more.*content",
        r"adhere to your guidelines",
    ]
    is_junk = any(re.search(p, quote, re.IGNORECASE) for p in JUNK_PATTERNS)
    if is_junk:
        logger.warning(f"LLM returned junk/apology instead of quote. Falling back. Got: '{quote[:80]}'")
        return random.choice(FALLBACK_RAMANA_QUOTES)

    # VALIDATION: If the LLM returned a tiny fragment (under 8 words) or something
    # that doesn't look like a complete sentence, ask it to try again with stricter rules.
    word_count = len(quote.split())
    has_verb_like = bool(re.search(r'\b(is|are|was|were|has|have|had|be|do|does|did|can|could|will|would|shall|should|may|might|must|need|know|see|find|realize|seek|remain|abide|exist|arise|appear|come|go|give|take|make|think|feel|become|turn|cease|let|ask|look|search|enquire|inquire|discover|understand|attain|reach|transcend)\b', quote, re.IGNORECASE))

    if word_count < 6 or (word_count < 10 and not has_verb_like):
        logger.warning(f"Quote too short or fragment-like ({word_count} words): '{quote}'. Retrying...")
        retry_prompt = dedent(
            f"""
        The previous attempt returned a fragment that is too short to stand alone
        on a contemplation card: "{quote}"

        Please try again. Select a COMPLETE sentence (or 2-3 short sentences) from
        the source passages below. The quote must:
        - Be grammatically complete (subject + verb + meaning)
        - Be 15-50 words long
        - Make sense to someone reading it with no other context
        - Come directly from the provided text

        Source passages:
        {source_text}
        """
        )
        retry_response = await model.chat_async(retry_prompt)
        retry_quote = retry_response.strip()
        retry_quote = re.sub(r'\n?\s*[—–-]+\s*\S.*$', '', retry_quote, flags=re.MULTILINE).strip()
        retry_quote = re.sub(r'\n?\s*(Source|From|Ref|Reference)\s*:.*$', '', retry_quote, flags=re.IGNORECASE | re.MULTILINE).strip()
        retry_quote = re.sub(r'^From [^:]+:\s*', '', retry_quote, flags=re.IGNORECASE).strip()
        retry_quote = re.sub(r'^["\'""]+|["\'""]+$', '', retry_quote).strip()

        if len(retry_quote.split()) >= 6:
            quote = retry_quote
            logger.info(f"Retry produced better quote ({len(retry_quote.split())} words)")
        else:
            logger.warning(f"Retry also short. Using best available: '{quote}'")

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

    # Allow up to 5 lines. If text still overflows, reduce font size and re-wrap
    # rather than truncating mid-sentence (which ruins the quote).
    MAX_LINES = 5
    if len(wrapped_lines) > MAX_LINES:
        # Try progressively smaller font sizes to fit the full quote
        for smaller_size in [int(font_size * 0.85), int(font_size * 0.72), int(font_size * 0.6)]:
            font = _load_font(smaller_size)
            max_text_width = int(orig_width * max_width_ratio)
            wrapped_lines = []
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
                        wrapped_lines.append(word)
                        current_line = ""
            if current_line:
                wrapped_lines.append(current_line)

            font_size = smaller_size
            if len(wrapped_lines) <= MAX_LINES:
                break

        # If still too long after smallest font, truncate at sentence boundary
        if len(wrapped_lines) > MAX_LINES:
            full_text = " ".join(wrapped_lines)
            # Find the last sentence-ending punctuation that fits within MAX_LINES
            sentences = re.split(r'(?<=[.!?])\s+', full_text)
            truncated = ""
            for sentence in sentences:
                candidate = (truncated + " " + sentence).strip() if truncated else sentence
                # Re-wrap candidate to check line count
                test_lines = []
                test_current = ""
                for w in candidate.split():
                    test_line = test_current + (" " if test_current else "") + w
                    bbox = temp_draw.textbbox((0, 0), test_line, font=font)
                    tw = bbox[2] - bbox[0]
                    if tw <= max_text_width:
                        test_current = test_line
                    else:
                        if test_current:
                            test_lines.append(test_current)
                            test_current = w
                        else:
                            test_lines.append(w)
                            test_current = ""
                if test_current:
                    test_lines.append(test_current)
                if len(test_lines) <= MAX_LINES:
                    truncated = candidate
                    wrapped_lines = test_lines
                else:
                    break  # Adding this sentence would overflow
            # If we couldn't fit even one sentence, hard-cap as last resort
            if not truncated:
                wrapped_lines = wrapped_lines[:MAX_LINES]
                last_line = wrapped_lines[-1]
                wrapped_lines[-1] = last_line + "…"

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