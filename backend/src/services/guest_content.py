"""
Guest content generation — card, audio, video — for unauthenticated landing-page visitors.

Rate limiting (both dimensions must pass):
  • session_id  — browser localStorage UUID, max GUEST_CONTENT_LIMIT per day
  • IP hash     — SHA-256 of client IP + ":content" namespace, max GUEST_CONTENT_LIMIT per day

Using both prevents:
  - Multiple tabs / incognito windows  → same IP hash, blocked
  - VPN per-request cycling            → each exit node gets its own counter
  - Browser reopen bypass              → localStorage UUID persists across sessions

Counters are persisted in the GuestSession DB table (same table as chat rate limiting)
using a ":content" namespace suffix so they never collide with chat rows.
Content files go to Supabase storage.
"""

import asyncio
import hashlib
import uuid
import time
import re
import random
import logging
import datetime as _dt
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Verified authentic Ramana Maharshi quotes — guaranteed clean fallback
# (mirrors FALLBACK_RAMANA_QUOTES in src/content/image.py)
_RAMANA_FALLBACK_QUOTES = [
    "Your own Self-Realization is the greatest service you can render the world.",
    "The mind is nothing but a bundle of thoughts. The thought 'I' is the root of all thoughts.",
    "Silence is also conversation.",
    "Happiness is the very nature of the Self; happiness and the Self are not different.",
    "The degree of freedom from unwanted thoughts and the degree of concentration on a single thought are the measures to gauge spiritual progress.",
    "Whatever is destined not to happen will not happen, try as you may. Whatever is destined to happen will happen, do what you may to prevent it.",
    "There is neither creation nor destruction, neither destiny nor free will, neither path nor achievement. This is the final truth.",
    "Realization is not acquisition of anything new nor is it a new faculty. It is only removal of all camouflage.",
    "Mind is consciousness which has put on limitations. You are originally unlimited and perfect. Later you take on limitations and become the mind.",
    "Be still. It is the wind that makes the water ripple. The Self remains unchanging in the midst of all activities.",
    "Turn your vision inward and then the whole world will be full of supreme Spirit.",
    "No one succeeds without effort. Those who succeed owe their success to perseverance.",
    "To know the Self is to be the Self, for the Self is consciousness.",
]

# Phrases that indicate AI meta-commentary, not a genuine teaching sentence.
# Any sentence whose lowercased text STARTS WITH one of these is discarded.
_JUNK_PREFIXES = (
    "here are", "these are", "the following", "below are", "here is",
    "let me", "i will", "i have", "i am", "i'm ", "i'd ",
    "based on", "according to", "in summary", "in conclusion",
    "to summarize", "to answer", "in response", "in short",
    "in essence", "for example", "for instance", "additionally",
    "furthermore", "moreover", "however", "nevertheless",
    "some insights", "some key", "key insights", "key points",
    "key takeaways", "important points",
    "first,", "second,", "third,", "finally,", "lastly,",
    "note that", "please note", "it is important", "it's important",
    "it should be", "one should", "one must",
)

# Regex patterns that mark a sentence as junk regardless of where they appear.
_JUNK_PATTERNS = [
    re.compile(r"^\s*\d+[\.\)]\s"),          # numbered list: "1. " or "1) "
    re.compile(r":\s*$"),                     # ends with colon (intro sentence)
    re.compile(r"\d+[\.\)]\s+\w"),            # inline numbered list mid-sentence
    re.compile(r"^[-•*]\s"),                  # bullet point
    # Encyclopedia / hollow descriptor sentences:
    # "Silence, in the teachings of X, is a profound concept."
    # "Silence is a profound and significant concept."
    # "X refers to / is defined as / is known as ..."
    re.compile(r"\bin the teachings of\b", re.IGNORECASE),
    re.compile(r"\baccording to ramana\b", re.IGNORECASE),
    re.compile(r"is a (profound|significant|central|core|key|fundamental|important|crucial)\b.*\b(concept|idea|principle|notion|teaching|practice|term|aspect)\b", re.IGNORECASE),
    re.compile(r"\b(refers to|is defined as|is known as|is described as|can be defined as|can be described as)\b", re.IGNORECASE),
    re.compile(r"\bplays (a|an) (important|key|central|significant|crucial) role\b", re.IGNORECASE),
    re.compile(r"\bin (his|the) (teaching|teachings|philosophy|tradition|framework|context|view)\b", re.IGNORECASE),
    re.compile(r"\baccording to (him|ramana|maharshi|this teaching)\b", re.IGNORECASE),
]

from fastapi import HTTPException, Depends
from fastapi import Request as FastAPIRequest
from pydantic import BaseModel

from src.db import GuestSession, get_db_session_fa


# ── Config ─────────────────────────────────────────────────────────────────────
GUEST_CONTENT_LIMIT = 3      # max items per session AND per IP per day
GUEST_AUDIO_LENGTH  = "3 min"
GUEST_VIDEO_LENGTH  = "3 min"

# Namespace suffix so content rows never collide with chat rows in GuestSession
_CONTENT_NS = ":content"


# ── In-memory store (content results only — not rate limits) ───────────────────
# { content_id: { status, content_url, content_type, error, created_at } }
_STORE: dict[str, dict] = {}


# ── Wire models ────────────────────────────────────────────────────────────────
class GuestContentRequest(BaseModel):
    question:   str
    answer:     str
    mode:       str   # "image" | "audio" | "video"
    session_id: str


class GuestContentResponse(BaseModel):
    content_id: str


class GuestContentStatus(BaseModel):
    content_id:   str
    status:       str            # pending | processing | complete | failed
    content_url:  str | None = None
    content_type: str | None = None
    error:        str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────
def _today() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


def _get_client_ip(http_request: FastAPIRequest) -> str:
    """Return the real client IP, respecting App Runner's X-Forwarded-For."""
    forwarded = http_request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if http_request.client:
        return http_request.client.host
    return "unknown"


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()


async def _db_check_and_bump(
    db_session: AsyncSession,
    ip_hash: str,
    sid: str,
    today: str,
) -> None:
    """Check content rate limits in the DB and increment if under limit.

    Uses GuestSession table with ":content" namespace so rows never
    collide with chat-rate-limit rows. Raises HTTPException 429 if
    either the IP or session has hit GUEST_CONTENT_LIMIT today.
    Falls back gracefully on any DB error (log + allow).
    """
    # Namespaced keys — distinct from chat rows
    ip_key  = _hash_ip(_get_client_ip.__name__ + ip_hash + _CONTENT_NS)  # avoids reuse
    ip_key  = hashlib.sha256((ip_hash + _CONTENT_NS).encode()).hexdigest()
    sid_key = f"content:{sid}"

    _LIMIT = {
        "code": "GUEST_CONTENT_LIMIT_REACHED",
        "message": (
            f"You've used all {GUEST_CONTENT_LIMIT} free generations for today. "
            "Sign up for unlimited access."
        ),
    }

    try:
        # ── IP check ──────────────────────────────────────────────────────────
        ip_row = (await db_session.execute(
            select(GuestSession).where(
                GuestSession.ip_hash == ip_key,
                GuestSession.session_date == today,
            ).limit(1)
        )).scalar_one_or_none()

        if ip_row and ip_row.message_count >= GUEST_CONTENT_LIMIT:
            logger.info(f"[GUEST_CONTENT] IP limit reached: {ip_hash[:8]}… count={ip_row.message_count}")
            raise HTTPException(status_code=429, detail=_LIMIT)

        # ── Session check ─────────────────────────────────────────────────────
        sid_row = (await db_session.execute(
            select(GuestSession).where(
                GuestSession.session_id == sid_key,
                GuestSession.session_date == today,
            ).limit(1)
        )).scalar_one_or_none()

        if sid_row and sid_row.message_count >= GUEST_CONTENT_LIMIT:
            logger.info(f"[GUEST_CONTENT] Session limit reached: {sid[:16]}… count={sid_row.message_count}")
            raise HTTPException(status_code=429, detail=_LIMIT)

        # ── Both passed — increment ───────────────────────────────────────────
        if ip_row:
            ip_row.message_count += 1
            ip_row.updated_at = _dt.datetime.utcnow()
            db_session.add(ip_row)
        else:
            db_session.add(GuestSession(
                ip_hash=ip_key, session_id=sid_key,
                session_date=today, message_count=1,
            ))

        if sid_row:
            sid_row.message_count += 1
            sid_row.updated_at = _dt.datetime.utcnow()
            db_session.add(sid_row)
        else:
            if ip_row is not None or sid_key != ip_key:
                db_session.add(GuestSession(
                    ip_hash=ip_key, session_id=sid_key,
                    session_date=today, message_count=1,
                ))

        await db_session.commit()

    except HTTPException:
        raise
    except Exception as exc:
        # DB error — log and allow (don't punish the user for infra issues)
        logger.error(f"[GUEST_CONTENT] DB rate-limit check failed: {exc}")
        await db_session.rollback()


def _is_junk(sentence: str) -> bool:
    """Return True if the sentence is AI meta-commentary rather than a teaching."""
    low = sentence.lower().strip()
    # Check blacklisted prefixes
    if any(low.startswith(p) for p in _JUNK_PREFIXES):
        return True
    # Check regex patterns
    for pat in _JUNK_PATTERNS:
        if pat.search(sentence):
            return True
    # Reject sentences with question marks (not quotable as card text)
    if sentence.strip().endswith("?"):
        return True
    return False


def _short_quote(answer: str, max_chars: int = 200) -> str:
    """Extract a clean, quotable 1–2 sentence caption from the AI answer.

    Strategy:
      1. Split the answer into sentences.
      2. Walk the list and collect the first clean sentence (40–max_chars,
         passes junk filter).
      3. If that sentence is short (< 90 chars) and the *next* sentence is
         also clean, append it — so the card caption feels complete.
         Combined length must stay within max_chars.
      4. If no clean sentence is found at all, fall back to a verified
         authentic Ramana quote.
    """
    sentences = [s.strip().strip('"').strip("'").strip()
                 for s in re.split(r'(?<=[.!?])\s+', answer.strip())]
    sentences = [s for s in sentences if s]

    for i, s in enumerate(sentences):
        if len(s) < 40 or len(s) > max_chars or _is_junk(s):
            continue
        # Found a good primary sentence.
        # If it's short, try to grab the next clean sentence too.
        if len(s) < 90 and i + 1 < len(sentences):
            nxt = sentences[i + 1]
            if not _is_junk(nxt) and len(nxt) >= 20:
                combined = f"{s} {nxt}"
                if len(combined) <= max_chars:
                    return combined
        return s

    # Nothing clean found — use a verified Ramana quote as the card caption.
    return random.choice(_RAMANA_FALLBACK_QUOTES)


async def _generate_guest_meditation_transcript(question: str, answer: str, length: str = "3 min") -> str:
    """Generate a meditation transcript laser-focused on the user's specific question.

    Unlike the general `generate_meditation_transcript_optimized` which treats source
    as generic spiritual text, this function explicitly tells the LLM to center every
    breath, every pause, every reflection on the exact question the seeker asked.
    This is the USP of the service: fully personalised content.
    """
    from textwrap import dedent
    from tuneapi import tt
    from src.settings import get_llm

    try:
        minutes = int(str(length).split()[0])
    except Exception:
        minutes = 3
    target_words = f"{minutes * 200}–{minutes * 220}"
    target_duration = f"{minutes}-minute"

    prompt = dedent(f"""
        You are writing a personalised guided meditation for a seeker.

        THEIR EXACT QUESTION:
        "{question}"

        RAMANA MAHARSHI'S TEACHING IN RESPONSE:
        "{answer}"

        TASK: Write a {target_duration} spoken meditation script (~{target_words} words) that is
        ENTIRELY built around the seeker's question above. Every line must connect back to
        their specific concern. Do NOT make this a generic meditation.

        STRUCTURE (do NOT write these labels in the script):
        1. Opening (first 20%): Name the seeker's concern directly. Invite them to bring their
           question into the body. Set the scene with stillness.
        2. Core (middle 60%): Dwell in the teaching above. Use vivid sensory language.
           Return to the specific theme of "{question[:60]}" at least three times.
           Expand every insight into breath, sensation, inner experience.
        3. Closing (final 20%): Draw the answer back to their heart. End with stillness
           and a sense of resolution or rest in the question itself.

        REQUIREMENTS:
        - Use [pause] and [breathing] tags frequently for natural pacing.
        - Speak directly to the seeker as "you".
        - Calm, unhurried, devotional tone.
        - Pure spoken script — no section headings, no labels, no asterisks.
        - Start immediately with spoken words (no preamble like "Here is your meditation").
    """).strip()

    model = get_llm("gpt-4o")
    thread = tt.Thread(
        tt.system("You write deeply personalised guided meditations. Every word serves the seeker's specific question."),
        id="guest_meditation",
    )
    thread.append(tt.Message(prompt, "user"))
    response = await model.chat_async(thread, max_tokens=2500)
    return response.content if hasattr(response, "content") else str(response)


def _signed_url(spb_client, path: str) -> str | None:
    try:
        result = spb_client.storage.from_("generations").create_signed_url(
            path, 86400  # 24 h
        )
        return result.get("signedURL")
    except Exception:
        return None


# ── Background generators ──────────────────────────────────────────────────────
async def _gen_image(content_id: str, question: str, answer: str):
    _STORE[content_id]["status"] = "processing"
    try:
        from src.content.image import (
            _generate_image_prompt_from_question,
            _get_random_repository_image,
            add_caption_to_image,
            CONTEMPLATION_PROMPTS,
            _generate_image,
        )
        from src.db import get_background_session
        from src.settings import get_supabase_admin_client, get_settings

        spb = get_supabase_admin_client(get_settings())

        try:
            prompt = await _generate_image_prompt_from_question(question)
        except Exception:
            prompt = random.choice(CONTEMPLATION_PROMPTS)

        quote = _short_quote(answer)

        async with get_background_session() as session:
            repo_img = await _get_random_repository_image(session, spb)

        pil_image = repo_img if repo_img is not None else await _generate_image(prompt)
        with_caption = add_caption_to_image(pil_image, quote)

        buf = BytesIO()
        with_caption.save(buf, format="PNG")
        path = f"guest-cards/{content_id}.png"
        spb.storage.from_("generations").upload(path, buf.getvalue(), {"content-type": "image/png"})

        _STORE[content_id].update(
            status="complete", content_url=_signed_url(spb, path), content_type="image"
        )
    except Exception as exc:
        _STORE[content_id].update(status="failed", error=str(exc))


async def _gen_audio(content_id: str, question: str, answer: str):
    _STORE[content_id]["status"] = "processing"
    try:
        from src.content.audio import (
            generate_audio_from_transcript_optimized,
            compress_audio_to_mp3_optimized,
        )
        from src.settings import get_supabase_admin_client, get_settings

        spb = get_supabase_admin_client(get_settings())

        # Use the guest-specific, question-centric transcript generator
        transcript  = await _generate_guest_meditation_transcript(question, answer, GUEST_AUDIO_LENGTH)
        audio_bytes = await generate_audio_from_transcript_optimized(transcript)
        compressed  = await compress_audio_to_mp3_optimized(audio_bytes)

        path = f"guest-audio/{content_id}.mp3"
        spb.storage.from_("generations").upload(path, compressed, {"content-type": "audio/mpeg"})

        _STORE[content_id].update(
            status="complete", content_url=_signed_url(spb, path), content_type="audio"
        )
    except Exception as exc:
        _STORE[content_id].update(status="failed", error=str(exc))


async def _gen_video(content_id: str, question: str, answer: str):
    _STORE[content_id]["status"] = "processing"
    try:
        import os
        from src.content.audio import (
            generate_audio_from_transcript_optimized,
        )
        from src.content.parallel_video import parallel_generator
        from src.db import get_background_session
        from src.settings import get_supabase_admin_client, get_settings

        spb = get_supabase_admin_client(get_settings())

        # Use the guest-specific, question-centric transcript generator
        transcript  = await _generate_guest_meditation_transcript(question, answer, GUEST_VIDEO_LENGTH)
        audio_bytes = await generate_audio_from_transcript_optimized(transcript)
        quote       = parallel_generator._extract_quote_from_transcript(transcript)

        async with get_background_session() as session:
            library_images = await parallel_generator._get_multiple_library_images(session, target_count=4)

        if library_images:
            video_path = await parallel_generator._create_ken_burns_video_with_quote(
                library_images, audio_bytes, quote
            )
        else:
            from src.content.image import _generate_image, CONTEMPLATION_PROMPTS
            pil_image  = await _generate_image(random.choice(CONTEMPLATION_PROMPTS))
            video_path = await parallel_generator._create_video_streaming_parallel(pil_image, transcript)

        with open(video_path, "rb") as f:
            video_data = f.read()
        try:
            os.unlink(video_path)
        except Exception:
            pass

        path = f"guest-video/{content_id}.mp4"
        spb.storage.from_("generations").upload(path, video_data, {"content-type": "video/mp4"})

        _STORE[content_id].update(
            status="complete", content_url=_signed_url(spb, path), content_type="video"
        )
    except Exception as exc:
        _STORE[content_id].update(status="failed", error=str(exc))


# ── Route handlers ─────────────────────────────────────────────────────────────
async def create_guest_content(
    http_request: FastAPIRequest,
    request: GuestContentRequest,
    db_session: AsyncSession = Depends(get_db_session_fa),
):
    """POST /api/content/guest — rate-limited by session_id AND IP hash (DB-persisted)."""
    sid  = (request.session_id or "").strip()
    mode = request.mode.strip().lower()

    if not sid:
        raise HTTPException(400, "session_id is required.")
    if mode not in ("image", "audio", "video"):
        raise HTTPException(400, "mode must be image, audio, or video.")
    if not request.question.strip() or not request.answer.strip():
        raise HTTPException(400, "question and answer are required.")

    # Layer 3 — log detected IP for debugging (first 8 chars of hash only)
    ip      = _get_client_ip(http_request)
    ip_hash = _hash_ip(ip)
    logger.info(f"[GUEST_CONTENT] request mode={mode} ip_prefix={ip_hash[:8]} sid_prefix={sid[:12]}")

    today = _today()

    # ── DB-persisted dual rate check (session + IP, namespaced :content) ────────
    await _db_check_and_bump(db_session, ip_hash, sid, today)

    # ── Rate checks passed — launch background generation task ─────────────────
    cid = str(uuid.uuid4())
    _STORE[cid] = {
        "status":       "pending",
        "content_url":  None,
        "content_type": mode,
        "error":        None,
        "created_at":   time.time(),
    }

    q, a = request.question, request.answer
    if mode == "image":
        asyncio.ensure_future(_gen_image(cid, q, a))
    elif mode == "audio":
        asyncio.ensure_future(_gen_audio(cid, q, a))
    else:
        asyncio.ensure_future(_gen_video(cid, q, a))

    return GuestContentResponse(content_id=cid)


async def get_guest_content(content_id: str):
    """GET /api/content/guest/{content_id}"""
    rec = _STORE.get(content_id)
    if not rec:
        raise HTTPException(404, "Content not found.")
    return GuestContentStatus(
        content_id=content_id,
        status=rec["status"],
        content_url=rec.get("content_url"),
        content_type=rec.get("content_type"),
        error=rec.get("error"),
    )
