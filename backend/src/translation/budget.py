"""Daily char-usage ledger + budget cap helpers.

Reads/writes the `translation_usage_daily` table. All operations are
SQLAlchemy 2.0 async via the existing AsyncSession.

Hard daily caps (configurable via Settings):
  • Sarvam: 60K chars/day → 1.8M/month (90% of free credit)
  • Azure:  60K chars/day → 1.8M/month (90% of 2M/month free tier)
  • Google: 15K chars/day → 450K/month (90% of 500K free tier)

Beyond cap, gateway returns source text with provider="quota_exceeded".
"""
from __future__ import annotations

import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from tuneapi import tu

from src.settings import Settings, get_settings
from src.translation.models import TranslationUsageDaily

ProviderName = Literal["sarvam", "azure", "google", "openai", "manual"]


# Per-provider cost ($/M chars) — used for the cost_estimate column.
_COST_PER_MILLION = {
    "sarvam": 24.0,
    "azure":  10.0,
    "google": 20.0,
    "openai": 12.0,
    "manual":  0.0,
}


def _daily_cap(provider: ProviderName, settings: Settings) -> int:
    """Return the daily char ceiling for this provider."""
    if provider == "sarvam":
        return settings.translation_daily_sarvam_cap
    if provider == "azure":
        return settings.translation_daily_azure_cap
    if provider == "google":
        return getattr(settings, "translation_daily_google_cap", 15_000)
    # OpenAI / manual have no cap here (different cost model)
    return 1_000_000


async def chars_used_today(session: AsyncSession, provider: ProviderName) -> int:
    """How many characters has this provider already used today?"""
    today = datetime.date.today()
    result = await session.execute(
        select(TranslationUsageDaily.chars_used).where(
            TranslationUsageDaily.usage_date == today,
            TranslationUsageDaily.provider == provider,
        )
    )
    row = result.scalar_one_or_none()
    return int(row) if row is not None else 0


async def can_spend(session: AsyncSession, provider: ProviderName, chars: int) -> bool:
    """True if (today's usage + chars) <= daily cap."""
    settings = get_settings()
    cap = _daily_cap(provider, settings)
    used = await chars_used_today(session, provider)
    return (used + chars) <= cap


async def increment_usage(
    session: AsyncSession,
    provider: ProviderName,
    chars: int,
) -> None:
    """Atomically add `chars` to today's row; insert if missing.

    Uses Postgres ON CONFLICT to avoid races between concurrent translation calls.
    """
    today = datetime.date.today()
    cost = (chars / 1_000_000.0) * _COST_PER_MILLION.get(provider, 0.0)

    stmt = pg_insert(TranslationUsageDaily.__table__).values(
        usage_date=today,
        provider=provider,
        chars_used=chars,
        api_calls=1,
        cost_estimate=cost,
    ).on_conflict_do_update(
        index_elements=["usage_date", "provider"],
        set_={
            "chars_used":    TranslationUsageDaily.__table__.c.chars_used + chars,
            "api_calls":     TranslationUsageDaily.__table__.c.api_calls + 1,
            "cost_estimate": TranslationUsageDaily.__table__.c.cost_estimate + cost,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def usage_summary(session: AsyncSession, days: int = 30) -> dict:
    """Return last-N-days usage rolled up by provider. Used by ops dashboard."""
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    result = await session.execute(
        select(
            TranslationUsageDaily.provider,
            TranslationUsageDaily.chars_used,
            TranslationUsageDaily.api_calls,
            TranslationUsageDaily.cost_estimate,
            TranslationUsageDaily.usage_date,
        ).where(TranslationUsageDaily.usage_date >= cutoff)
         .order_by(TranslationUsageDaily.usage_date.desc())
    )
    rows = result.all()
    summary = {}
    for r in rows:
        prov = r.provider
        if prov not in summary:
            summary[prov] = {"chars": 0, "calls": 0, "cost": 0.0, "days": 0}
        summary[prov]["chars"] += int(r.chars_used or 0)
        summary[prov]["calls"] += int(r.api_calls or 0)
        summary[prov]["cost"]  += float(r.cost_estimate or 0)
        summary[prov]["days"]  += 1
    return summary
