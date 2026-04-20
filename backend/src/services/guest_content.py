"""
Guest content generation — card, audio, video — for unauthenticated landing-page visitors.

Rate limiting (both dimensions must pass):
  • session_id  — browser sessionStorage UUID, max GUEST_CONTENT_LIMIT per day
  • IP hash     — SHA-256 of client IP, max GUEST_CONTENT_LIMIT per day

Using both prevents:
  - Multiple tabs / incognito windows  → same IP hash, blocked
  - VPN per-request cycling            → each exit node gets its own counter

Counters are in-memory (reset on restart); content files go to Supabase storage.
"""

import asyncio
import hashlib
import uuid
import time
import re
import random
from io import BytesIO

from fastapi import HTTPException
from fastapi import Request as FastAPIRequest
from pydantic import BaseModel


# ── Config ─────────────────────────────────────────────────────────────────────
GUEST_CONTENT_LIMIT = 3      # max items per session AND per IP per day
GUEST_AUDIO_LENGTH  = "3 min"
GUEST_VIDEO_LENGTH  = "3 min"


# ── In-memory stores ───────────────────────────────────────────────────────────
# { content_id: { status, content_url, content_type, error, created_at } }
_STORE: dict[str, dict] = {}

# { session_id:  { "YYYY-MM-DD": count } }
_SESSION_RATE: dict[str, dict] = {}

# { ip_hash:     { "YYYY-MM-DD": count } }
_IP_RATE: dict[str, dict] = {}


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
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _rate_ok(key: str, store: dict) -> bool:
    """Return True if the key is under the daily limit."""
    return store.setdefault(key, {}).get(_today(), 0) < GUEST_CONTENT_LIMIT


def _rate_bump(key: str, store: dict):
    """Increment the daily counter for key in store."""
    counts = store.setdefault(key, {})
    today = _today()
    counts[today] = counts.get(today, 0) + 1


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


def _short_quote(answer: str, max_chars: int = 160) -> str:
    """Extract the most quotable sentence from the AI answer."""
    sentences = re.split(r'(?<=[.!?])\s+', answer.strip())
    for s in sentences:
        clean = s.strip().strip('"').strip("'")
        if 40 <= len(clean) <= max_chars:
            return clean
    return (answer[:max_chars].rsplit(' ', 1)[0] + '…') if len(answer) > max_chars else answer


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
            generate_meditation_transcript_optimized,
            generate_audio_from_transcript_optimized,
            compress_audio_to_mp3_optimized,
        )
        from src.settings import get_supabase_admin_client, get_settings

        spb = get_supabase_admin_client(get_settings())
        source = f"Question from seeker: {question}\n\nTeaching from Bhagavan: {answer}"

        transcript  = await generate_meditation_transcript_optimized(source, GUEST_AUDIO_LENGTH)
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
            generate_meditation_transcript_optimized,
            generate_audio_from_transcript_optimized,
        )
        from src.content.parallel_video import parallel_generator
        from src.db import get_background_session
        from src.settings import get_supabase_admin_client, get_settings

        spb = get_supabase_admin_client(get_settings())
        source = f"Question from seeker: {question}\n\nTeaching from Bhagavan: {answer}"

        transcript  = await generate_meditation_transcript_optimized(source, GUEST_VIDEO_LENGTH)
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
async def create_guest_content(http_request: FastAPIRequest, request: GuestContentRequest):
    """POST /api/content/guest — rate-limited by session_id AND IP hash."""
    sid  = (request.session_id or "").strip()
    mode = request.mode.strip().lower()

    if not sid:
        raise HTTPException(400, "session_id is required.")
    if mode not in ("image", "audio", "video"):
        raise HTTPException(400, "mode must be image, audio, or video.")
    if not request.question.strip() or not request.answer.strip():
        raise HTTPException(400, "question and answer are required.")

    # ── Rate check: session_id ─────────────────────────────────────────────────
    if not _rate_ok(sid, _SESSION_RATE):
        raise HTTPException(
            429,
            f"You've used all {GUEST_CONTENT_LIMIT} free generations for today. "
            "Sign up for unlimited access."
        )

    # ── Rate check: IP hash ────────────────────────────────────────────────────
    ip      = _get_client_ip(http_request)
    ip_hash = _hash_ip(ip)
    if not _rate_ok(ip_hash, _IP_RATE):
        raise HTTPException(
            429,
            f"You've used all {GUEST_CONTENT_LIMIT} free generations for today. "
            "Sign up for unlimited access."
        )

    # ── Both passed — bump counters and launch background task ─────────────────
    _rate_bump(sid,     _SESSION_RATE)
    _rate_bump(ip_hash, _IP_RATE)

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
