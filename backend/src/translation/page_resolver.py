"""GET /api/page/{slug}?lang=xx — translated long-form page content.

Frontend uses this to fetch the translated body of articles, teaching pages,
about pages, etc. The resolver:

  1. Loads the canonical English source (via a pluggable fetcher — see
     `_fetch_source_page` below; default uses src.db.SourceDocument or
     a `pages` table if you have one).
  2. Looks up the cache for (slug, lang).
  3. If cached AND source hash matches → return cached row.
  4. If miss → call the gateway internally to translate, cache, return.

The fetcher is pluggable so this works regardless of where your CMS content
lives — adapt _fetch_source_page() to your actual data source.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session_fa
from src import wire as w
from src.translation import budget, cache, PHASE_1_LANGS
from src.translation.gateway import _primary_provider, _try_provider
from src.translation.providers import length_ratio_anomaly

log = logging.getLogger("translation.page_resolver")

router = APIRouter(tags=["translation"])


# ---------------------------------------------------------------------------
# Pluggable source-content fetcher
# ---------------------------------------------------------------------------

class SourcePage(BaseModel):
    slug: str
    title: str
    body: str
    last_updated: Optional[str] = None
    metadata: dict = {}


async def _fetch_source_page(session: AsyncSession, slug: str) -> Optional[SourcePage]:
    """Fetch the canonical (English) version of a page.

    DEFAULT IMPLEMENTATION:
      Try `pages` table first (if it exists), then fall back to SourceDocument
      (the RAG corpus) by name.

    ADAPT THIS to wherever the canonical content for translation actually lives
    in your wisdom-AI codebase. The translation system is content-source-agnostic.
    """
    # 1. Try a `pages` table — common pattern for static content. If your DB
    #    doesn't have one yet, create one or change this fetcher.
    try:
        from sqlalchemy import text as sql_text
        result = await session.execute(
            sql_text("""
                SELECT slug, title, body, last_updated::text, metadata
                FROM pages
                WHERE slug = :slug AND published = TRUE
                LIMIT 1
            """),
            {"slug": slug},
        )
        row = result.one_or_none()
        if row:
            return SourcePage(
                slug=row.slug,
                title=row.title or "",
                body=row.body or "",
                last_updated=row.last_updated,
                metadata=row.metadata or {},
            )
    except Exception as e:
        log.debug("pages table fetch failed (table may not exist): %s", e)

    # 2. Fall back to SourceDocument by name (RAG corpus)
    try:
        from src.db import SourceDocument
        result = await session.execute(
            select(SourceDocument).where(SourceDocument.name == slug).limit(1)
        )
        doc = result.scalar_one_or_none()
        if doc:
            return SourcePage(
                slug=slug,
                title=getattr(doc, "title", "") or "",
                body=getattr(doc, "description", "") or "",
                last_updated=getattr(doc, "created_at", None) and str(doc.created_at) or None,
                metadata={},
            )
    except Exception as e:
        log.debug("SourceDocument fetch failed: %s", e)

    return None


# ---------------------------------------------------------------------------
# Translation helper (uses the same provider chain as the gateway)
# ---------------------------------------------------------------------------

async def _translate_with_failover(
    session: AsyncSession,
    text: str,
    target_lang: str,
) -> tuple[str, str, float]:
    """Translate one piece of text through the provider chain.

    Returns: (translated_text, provider_used, quality_score)
    Raises HTTPException on full failure.
    """
    if not text or not text.strip():
        return ("", "noop", 1.0)

    primary = _primary_provider(target_lang)
    secondary = "azure" if primary == "sarvam" else "sarvam"
    chain = [primary, secondary, "google"]

    for prov in chain:
        if not await budget.can_spend(session, prov, len(text)):
            continue
        translated = await _try_provider(prov, text, target_lang, "en")
        if translated:
            await budget.increment_usage(session, prov, len(text))
            quality = 0.7 if length_ratio_anomaly(text, translated) else 0.9
            return (translated, prov, quality)

    # Graceful degradation — return source
    return (text, "quota_exceeded", 0.0)


# ---------------------------------------------------------------------------
# Main route
# ---------------------------------------------------------------------------

@router.get("/api/page/{slug}")
async def get_translated_page(
    slug: str,
    lang: str = Query("en", description="Target language code"),
    session: AsyncSession = Depends(get_db_session_fa),
) -> dict:
    """Return the page in the requested language, translating + caching on demand."""

    if lang not in PHASE_1_LANGS:
        raise HTTPException(400, detail={
            "code": "UNSUPPORTED_LANGUAGE",
            "message": f"Language '{lang}' not enabled in Phase 1",
            "details": {"supported": sorted(PHASE_1_LANGS)},
        })

    # Fetch the canonical English page first — the resolver relies on this as the source
    source = await _fetch_source_page(session, slug)
    if not source:
        raise HTTPException(404, detail={
            "code": "PAGE_NOT_FOUND",
            "message": f"No page found for slug '{slug}'",
            "details": None,
        })

    # English requested → return source directly
    if lang == "en":
        return w.SuccessResponse(
            success=True, message="OK",
            data={
                "slug":         source.slug,
                "language":     "en",
                "title":        source.title,
                "body":         source.body,
                "provider":     "source",
                "cached":       False,
                "last_updated": source.last_updated,
            },
        ).model_dump()

    # Cache check on (slug, lang)
    cached = await cache.lookup_by_resource(
        session, domain="coin", resource_type="page",
        resource_id=slug, target_lang=lang,
    )
    if cached:
        return w.SuccessResponse(
            success=True, message="Cache hit",
            data={
                "slug":          slug,
                "language":      lang,
                "title":         cached.translated_title or source.title,
                "body":          cached.translated_body,
                "provider":      cached.provider,
                "cached":        True,
                "last_updated":  cached.last_updated.isoformat() if cached.last_updated else None,
            },
        ).model_dump()

    # Translate title + body in parallel-ish (sequential is fine for now)
    title_translated, _, _ = await _translate_with_failover(session, source.title, lang)
    body_translated, provider, quality = await _translate_with_failover(session, source.body, lang)

    # Cache the result
    try:
        await cache.upsert(
            session,
            domain="coin",
            resource_type="page",
            resource_id=slug,
            language_code=lang,
            source_text=source.body,            # hash on body so source-change detection works
            translated_body=body_translated,
            translated_title=title_translated,
            provider=provider,
            quality_score=quality,
        )
    except Exception as e:
        log.error("Page cache upsert failed for %s/%s: %s", slug, lang, e)

    return w.SuccessResponse(
        success=True, message="Translated",
        data={
            "slug":         slug,
            "language":     lang,
            "title":        title_translated,
            "body":         body_translated,
            "provider":     provider,
            "cached":       False,
            "last_updated": None,
        },
    ).model_dump()
