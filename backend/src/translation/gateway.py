"""POST /api/translate — the translation gateway.

Composes providers + cache + budget into the failover-aware pipeline:
  1. Empty / same-language → no-op
  2. Postgres cache lookup → if hit, return cached row
  3. Provider selection: Sarvam for Indic, Azure for international
  4. Budget check → primary path; if blocked, try secondary/tertiary
  5. Provider call (with retries on transient errors)
  6. Quality heuristic (length-ratio anomaly) → adjust quality_score
  7. Cache the result + increment usage ledger
  8. Return SuccessResponse envelope

Public path (no JWT auth) when called from the React app for static UI strings;
authenticated when called for user-specific content. Add to public_paths IF you
want the front-end to call it without a token.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session_fa
from src import wire as w
from src.translation import budget, cache
from src.translation.providers import (
    call_sarvam,
    call_azure,
    call_google,
    length_ratio_anomaly,
)
from src.translation import INDIC_LANGS, PHASE_1_LANGS

log = logging.getLogger("translation.gateway")

router = APIRouter(tags=["translation"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class TranslateRequest(BaseModel):
    text: str = Field(..., description="Source text to translate")
    source_lang: str = Field("en", description="Source language code (default 'en')")
    target_lang: str = Field(..., description="Target language code")
    resource_type: str = Field("inline", description="What kind of content this is — 'page', 'ui_string', 'inline'")
    resource_id: Optional[str] = Field(None, description="Stable identifier if this content has one (slug, etc.)")
    domain: str = Field("coin", description="Site domain — 'coin' or 'in'")


class TranslateResponseData(BaseModel):
    translated: str
    cached: bool
    provider: str
    quality_score: Optional[float]


# ---------------------------------------------------------------------------
# Provider routing
# ---------------------------------------------------------------------------

def _primary_provider(target_lang: str) -> str:
    """Pick the primary provider based on target language."""
    return "sarvam" if target_lang in INDIC_LANGS else "azure"


async def _try_provider(provider: str, text: str, target: str, source: str) -> Optional[str]:
    """Call one provider; return translation or None on failure."""
    try:
        if provider == "sarvam":
            return await call_sarvam(text, target, source)
        if provider == "azure":
            return await call_azure(text, target, source)
        if provider == "google":
            return await call_google(text, target, source)
    except Exception as e:
        log.warning("Provider %s failed for %s: %s", provider, target, e)
        return None
    return None


# ---------------------------------------------------------------------------
# Main route
# ---------------------------------------------------------------------------

@router.post("/api/translate")
async def translate_endpoint(
    request: TranslateRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> dict:
    """Translate `text` from source_lang to target_lang with caching + failover."""

    # Validation
    if not request.text or not request.text.strip():
        return w.SuccessResponse(
            success=True, message="Empty input",
            data={"translated": "", "cached": False, "provider": "noop", "quality_score": None}
        ).model_dump()

    if request.source_lang == request.target_lang:
        return w.SuccessResponse(
            success=True, message="Same language",
            data={"translated": request.text, "cached": False, "provider": "noop", "quality_score": None}
        ).model_dump()

    if request.target_lang not in PHASE_1_LANGS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UNSUPPORTED_LANGUAGE",
                "message": f"Language '{request.target_lang}' is not enabled in Phase 1",
                "details": {"supported": sorted(PHASE_1_LANGS)},
            },
        )

    # 1. Cache lookup
    cached = await cache.lookup(session, request.text, request.target_lang)
    if cached is not None:
        return w.SuccessResponse(
            success=True, message="Cache hit",
            data={
                "translated":   cached.translated_body,
                "cached":       True,
                "provider":     cached.provider,
                "quality_score": cached.quality_score,
            },
        ).model_dump()

    # 2. Provider selection + failover
    primary = _primary_provider(request.target_lang)
    secondary = "azure" if primary == "sarvam" else "sarvam"
    tertiary = "google"

    chain = [primary, secondary, tertiary]
    translated: Optional[str] = None
    used_provider: Optional[str] = None

    for prov in chain:
        # Budget gate per provider
        if not await budget.can_spend(session, prov, len(request.text)):
            log.info("Budget cap hit for %s, skipping", prov)
            continue
        translated = await _try_provider(prov, request.text, request.target_lang, request.source_lang)
        if translated:
            used_provider = prov
            await budget.increment_usage(session, prov, len(request.text))
            break

    if translated is None:
        # Graceful degradation — return source text, NOT 5xx
        return w.SuccessResponse(
            success=True,
            message="All providers exhausted; returning source text",
            data={
                "translated": request.text,
                "cached": False,
                "provider": "quota_exceeded",
                "quality_score": None,
            },
        ).model_dump()

    # 3. Quality heuristic
    quality_score = 0.7 if length_ratio_anomaly(request.text, translated) else 0.9

    # 4. Cache (skip for very short / inline strings if you want, but caching is safe)
    if quality_score >= 0.5:
        try:
            await cache.upsert(
                session,
                domain=request.domain,
                resource_type=request.resource_type,
                resource_id=request.resource_id or "anonymous",
                language_code=request.target_lang,
                source_text=request.text,
                translated_body=translated,
                provider=used_provider,
                quality_score=quality_score,
            )
        except Exception as e:
            # Don't block the user response on a cache write failure
            log.error("Cache upsert failed: %s", e)

    return w.SuccessResponse(
        success=True, message="Translated",
        data={
            "translated":    translated,
            "cached":        False,
            "provider":      used_provider,
            "quality_score": quality_score,
        },
    ).model_dump()
