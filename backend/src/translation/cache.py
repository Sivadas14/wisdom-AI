"""Postgres cache lookup + upsert for translations.

The L2 cache (Redis intentionally absent in Phase 1). All translation reads
go: lookup → if hit, return; if miss, call provider, upsert here.

Concurrency-safe via Postgres ON CONFLICT — multiple workers translating
the same string at the same moment will end up with one row, not duplicates.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.translation.models import PageTranslation


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_source(text: str) -> str:
    """Stable SHA-256 of normalized source text."""
    normalized = (text or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

async def lookup(
    session: AsyncSession,
    source_text: str,
    target_lang: str,
) -> Optional[PageTranslation]:
    """Find a cached translation by (source_text_hash, language).

    Returns the FIRST match — for the same English source there may be multiple
    page_translations rows (different resource_ids); we'll happily return any
    of them since the translated text is identical.
    """
    src_hash = hash_source(source_text)
    result = await session.execute(
        select(PageTranslation)
        .where(
            PageTranslation.source_text_hash == src_hash,
            PageTranslation.language_code == target_lang,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def lookup_by_resource(
    session: AsyncSession,
    domain: str,
    resource_type: str,
    resource_id: str,
    target_lang: str,
) -> Optional[PageTranslation]:
    """Resource-keyed lookup — used by /api/page/{slug} for full pages."""
    result = await session.execute(
        select(PageTranslation)
        .where(
            PageTranslation.domain == domain,
            PageTranslation.resource_type == resource_type,
            PageTranslation.resource_id == resource_id,
            PageTranslation.language_code == target_lang,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

async def upsert(
    session: AsyncSession,
    *,
    domain: str = "coin",
    resource_type: str,
    resource_id: str,
    language_code: str,
    source_text: str,
    translated_body: str,
    provider: str,
    quality_score: float = 0.9,
    translated_title: Optional[str] = None,
) -> PageTranslation:
    """Insert or update the cached translation.

    Manual-override rows are protected — `WHERE manual_override = FALSE` prevents
    automated calls from clobbering admin edits.
    """
    src_hash = hash_source(source_text)

    stmt = pg_insert(PageTranslation.__table__).values(
        domain=domain,
        resource_type=resource_type,
        resource_id=resource_id,
        language_code=language_code,
        source_text_hash=src_hash,
        source_text=source_text,
        translated_title=translated_title,
        translated_body=translated_body,
        provider=provider,
        quality_score=quality_score,
        char_count=len(source_text),
    ).on_conflict_do_update(
        index_elements=["domain", "resource_type", "resource_id", "language_code"],
        set_={
            "source_text_hash": src_hash,
            "source_text": source_text,
            "translated_title": translated_title,
            "translated_body": translated_body,
            "provider": provider,
            "quality_score": quality_score,
            "char_count": len(source_text),
            "last_updated": pg_insert(PageTranslation.__table__).excluded.last_updated,
        },
        where=(PageTranslation.__table__.c.manual_override.is_(False)),
    )
    await session.execute(stmt)
    await session.commit()

    # Return the row we just wrote
    refreshed = await lookup_by_resource(
        session, domain, resource_type, resource_id, language_code
    )
    return refreshed  # type: ignore[return-value]
