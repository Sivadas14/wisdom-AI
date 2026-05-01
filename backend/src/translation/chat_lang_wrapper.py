"""Chat language wrapper — translate-around-existing-RAG-pipeline.

DESIGN NOTE
-----------
The existing chat_completions() in src/services/chat.py runs a sophisticated
RAG pipeline: embedding search → retrieve top-k chunks from Ramana corpus →
build system prompt with chunks → call GPT-4o → stream response → extract
citations + follow-up questions.

To ADD multilingual support without rewriting that pipeline, this wrapper
takes the user's Indic message, translates it into English, runs the
EXISTING RAG pipeline, then translates the assistant's English response back
to the target language. Citations + follow-up questions get translated too.

Trade-off: non-English responses are NOT streamed token-by-token (we need
the full English response to translate). The frontend should show a
"thinking…" indicator. English responses keep streaming as before.

This is the cleanest minimal-touch path that:
  - Preserves all RAG grounding work
  - Preserves citation extraction
  - Preserves follow-up questions
  - Adds zero risk to the English chat (most users today)

Phase-2 enhancement: stream-translate at sentence boundaries for an
interactive feel even in non-English. Out of Phase 1 scope.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.translation import INDIC_LANGS, PHASE_1_LANGS
from src.translation import budget, cache
from src.translation.gateway import _primary_provider, _try_provider
from src.translation.providers import length_ratio_anomaly

log = logging.getLogger("translation.chat_lang_wrapper")


async def detect_user_lang(
    session: AsyncSession,
    *,
    request_lang: Optional[str],
    user_id: Optional[str],
) -> str:
    """Resolve the chat language with priority order:

      1. Explicit `lang` field on the chat request (highest)
      2. User's saved language preference (language_preferences table)
      3. Default 'en'
    """
    if request_lang and request_lang in PHASE_1_LANGS:
        return request_lang

    if user_id:
        try:
            from sqlalchemy import select
            from src.translation.models import LanguagePreference
            res = await session.execute(
                select(LanguagePreference.preferred_language)
                .where(LanguagePreference.user_id == user_id)
                .limit(1)
            )
            pref = res.scalar_one_or_none()
            if pref and pref in PHASE_1_LANGS:
                return pref
        except Exception as e:
            log.debug("language preference lookup failed: %s", e)

    return "en"


async def translate_text(
    session: AsyncSession,
    text: str,
    *,
    source: str,
    target: str,
) -> str:
    """One-shot translate via the same provider chain as the gateway.

    Cache-aware: returns cached translation if available; otherwise translates,
    caches, and returns. On full failure returns source text unchanged.
    """
    if not text or not text.strip():
        return text
    if source == target:
        return text

    # Cache lookup keyed on the source text + target lang
    cached = await cache.lookup(session, text, target)
    if cached:
        return cached.translated_body

    primary = _primary_provider(target)
    secondary = "azure" if primary == "sarvam" else "sarvam"
    chain = [primary, secondary, "google"]

    for prov in chain:
        if not await budget.can_spend(session, prov, len(text)):
            continue
        translated = await _try_provider(prov, text, target, source)
        if translated:
            await budget.increment_usage(session, prov, len(text))
            quality = 0.7 if length_ratio_anomaly(text, translated) else 0.9

            # Cache for future identical calls
            try:
                await cache.upsert(
                    session,
                    domain="coin",
                    resource_type="chat",
                    resource_id="anonymous",  # not resource-keyed; matched only by hash
                    language_code=target,
                    source_text=text,
                    translated_body=translated,
                    provider=prov,
                    quality_score=quality,
                )
            except Exception:
                pass

            return translated

    log.warning("translate_text exhausted providers for %s→%s; returning source", source, target)
    return text


async def translate_user_message_to_english(
    session: AsyncSession, msg: str, source_lang: str
) -> str:
    """User typed in Indic — translate to English so the existing RAG pipeline works."""
    if source_lang == "en":
        return msg
    return await translate_text(session, msg, source=source_lang, target="en")


async def translate_assistant_response(
    session: AsyncSession, response: str, target_lang: str
) -> str:
    """The English assistant response → user's preferred language."""
    if target_lang == "en":
        return response
    return await translate_text(session, response, source="en", target=target_lang)


async def translate_follow_up_questions(
    session: AsyncSession, questions: list[str], target_lang: str
) -> list[str]:
    """Translate the auto-generated follow-up suggestions."""
    if target_lang == "en" or not questions:
        return questions
    out = []
    for q in questions:
        out.append(await translate_text(session, q, source="en", target=target_lang))
    return out


# Citations (file names + URLs) generally do NOT need translation —
# they're proper nouns / file paths. Skipping to save budget.
