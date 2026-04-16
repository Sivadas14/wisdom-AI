"""
Today's Contemplation — daily-rotating, LLM-generated Ramana-inspired
quote + inquiry question, cached per calendar day (IST).

Flow:
  GET /api/contemplation/today
    1. Compute today's date in Asia/Kolkata → YYYY-MM-DD
    2. SELECT from daily_contemplations WHERE date_key = today
       - if present: return it (fast path, no LLM call)
    3. Otherwise call the LLM to generate quote + question, INSERT, return
    4. On LLM failure: return a pre-written fallback (UI never breaks).

Public endpoint (no auth) — the contemplation is the same for every user
on a given day, and this endpoint may later be used by unauthenticated
email-delivery workers.
"""

from __future__ import annotations

import datetime
import json
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from tuneapi import tu, tt

from src.db import DailyContemplation, get_db_session
from src.settings import get_llm


router = APIRouter(prefix="/api/contemplation", tags=["Contemplation"])


# India Standard Time = UTC+5:30. We use a fixed offset rather than
# ZoneInfo("Asia/Kolkata") because the tzdata package is not guaranteed
# to be present in the slim Docker image.
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


# Hardcoded fallback so the endpoint ALWAYS returns something readable
# even if the LLM call fails or times out. Intentionally generic so it
# reads reasonably on any date.
_FALLBACK = {
    "quote": (
        "Silence is the true teaching. Sit quietly, and notice what remains "
        "when thought subsides."
    ),
    "question": "Who is the one who is aware right now?",
}


class ContemplationResponse(BaseModel):
    date: str          # YYYY-MM-DD in IST
    quote: str
    question: str


def _today_ist() -> str:
    """Return today's date in Asia/Kolkata as YYYY-MM-DD."""
    return datetime.datetime.now(tz=IST).date().isoformat()


def _extract_json(text: str) -> dict | None:
    """Best-effort JSON parse — LLMs sometimes wrap JSON in prose or fences.

    Strategy:
      1. Try straight json.loads on the whole string.
      2. Strip ```json ... ``` fences if present and retry.
      3. Regex-scan for the first balanced {...} block and parse that.
    """
    text = (text or "").strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    if fenced != text:
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass

    # Last resort: find the first {...} block
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


async def _generate_via_llm(date_key: str) -> tuple[str, str]:
    """Ask the LLM for today's contemplation. Returns (quote, question).

    Raises on unparseable output so the caller can fall back cleanly.
    """
    model = get_llm("gpt-4o")

    system_prompt = (
        "You are a contemplative teacher in the lineage of Bhagavan Ramana "
        "Maharshi. You produce a single 'Today's Contemplation' as compact "
        "JSON when asked. You never add preamble, commentary, or markdown "
        "fences — only the JSON object."
    )

    user_prompt = (
        f"Create today's contemplation for date {date_key}. "
        "Output ONLY this JSON object, nothing else:\n\n"
        "{\n"
        '  "quote": "A short contemplation (1 to 2 sentences, under 30 '
        "words) grounded in Ramana Maharshi's core teachings: self-inquiry, "
        "the awareness that precedes thought, the Heart, silence, or the "
        "sense 'I am'. Express the theme in clear modern English rather "
        'than fabricating a verbatim historical quote.",\n'
        '  "question": "A single self-inquiry question, under 15 words, '
        "that invites the reader to turn attention inward. Avoid yes/no "
        'questions and generic prompts."\n'
        "}\n\n"
        "Make today distinctive — vary wording from common phrasings. "
        "Plain text only, no quotation marks inside the values, no em-dashes."
    )

    thread = tt.Thread(
        tt.system(system_prompt),
        id=f"daily_contemplation_{date_key}",
    )
    thread.append(tt.Message(user_prompt, "user"))

    response = await model.chat_async(thread)
    raw = response.content if hasattr(response, "content") else str(response)

    parsed = _extract_json(raw)
    if not parsed or not isinstance(parsed, dict):
        raise ValueError(f"LLM returned unparseable JSON: {raw[:200]!r}")

    quote = str(parsed.get("quote", "")).strip()
    question = str(parsed.get("question", "")).strip()

    if not quote or not question:
        raise ValueError(f"LLM JSON missing quote/question: {parsed!r}")

    # Defensive trimming — the prompt says under 30 / under 15 words but
    # don't trust it completely. Hard cap at 400 / 200 chars.
    quote = quote[:400]
    question = question[:200]

    return quote, question


@router.get("/today", response_model=ContemplationResponse)
async def get_today_contemplation(
    db: AsyncSession = Depends(get_db_session),
) -> ContemplationResponse:
    """Return today's contemplation, generating and caching if needed."""
    date_key = _today_ist()

    # Fast path: already generated today.
    existing = await db.scalar(
        select(DailyContemplation).where(DailyContemplation.date_key == date_key)
    )
    if existing:
        return ContemplationResponse(
            date=date_key,
            quote=existing.quote,
            question=existing.question,
        )

    # Slow path: generate via LLM.
    try:
        quote, question = await _generate_via_llm(date_key)
    except Exception as e:
        tu.logger.warning(
            f"Contemplation LLM generation failed for {date_key}: {e}. "
            f"Falling back to default."
        )
        quote, question = _FALLBACK["quote"], _FALLBACK["question"]

    # Race-safe insert: if a concurrent request inserted first, the UNIQUE
    # constraint on date_key trips an IntegrityError and we re-fetch.
    row = DailyContemplation(date_key=date_key, quote=quote, question=question)
    db.add(row)
    try:
        await db.commit()
        await db.refresh(row)
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(DailyContemplation).where(DailyContemplation.date_key == date_key)
        )
        if existing:
            return ContemplationResponse(
                date=date_key,
                quote=existing.quote,
                question=existing.question,
            )
        # Shouldn't happen — integrity error but no row. Return what we
        # generated in-memory rather than erroring out.
        return ContemplationResponse(date=date_key, quote=quote, question=question)

    return ContemplationResponse(
        date=date_key,
        quote=row.quote,
        question=row.question,
    )
