"""
media_access.py — who may generate audio or video, and at what cost.

WHY THIS IS SEPARATE
--------------------
The decision has four sources of truth that must be consulted in a fixed order,
and putting that order inline in the request handler would have hidden it. Read
top to bottom, this file IS the policy:

    1. Admin              — free. Needed to exercise the pipelines, which fail
                            quietly rather than loudly.
    2. Trial grant        — free, for the duration of the grant.
    3. Legacy subscriber  — free. Whoever paid for a plan keeps what they paid
                            for, indefinitely, without the plan being sold.
    4. Everyone else      — credits.

Contemplation cards never appear here. They are free for everyone, guests
included, because a card draws on the image repository and costs a fraction of
a rupee. Metering it would cost more in goodwill than it could recover.

WHAT "MINUTES" MEANS
--------------------
The request carries a length like "5 min". Cost is linear in minutes because
text-to-speech is billed per minute of audio produced, so the length is what
decides the price, not the medium: a twenty-minute audio and a twenty-minute
video cost the same to make and cost the same in credits.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.db import PlanType, UserProfile, UserRole
from src.llm_shim import tu
from src.services import credits as C

# When a length is missing or unparseable, fall back to the shortest offered
# rather than the longest. Guessing high would overcharge someone for a
# malformed request; guessing low costs us a few rupees at worst.
DEFAULT_MINUTES = 5


def parse_minutes(length: Optional[str]) -> int:
    """"5 min" -> 5. Anything unrecognised falls back to the shortest option."""
    if not length:
        return DEFAULT_MINUTES
    m = re.search(r"(\d{1,3})", str(length))
    if not m:
        return DEFAULT_MINUTES
    minutes = int(m.group(1))
    return minutes if minutes > 0 else DEFAULT_MINUTES


@dataclass(frozen=True)
class MediaDecision:
    allowed: bool
    cost: int                    # credits this generation would consume
    reason: str                  # admin | trial | legacy_plan | credits | insufficient
    balance: int = 0
    charge: bool = False         # whether the caller should debit


async def decide(
    user: UserProfile,
    minutes: int,
    session: AsyncSession,
) -> MediaDecision:
    """Resolve whether this seeker may generate media of this length."""
    cost = C.credits_for_minutes(minutes)

    if getattr(user, "role", None) == UserRole.ADMIN:
        return MediaDecision(allowed=True, cost=cost, reason="admin")

    # A live trial grant. Read defensively: a failure to read grants must not
    # cost someone their access, but must not silently open the gates either,
    # so it falls through to the paid checks below rather than allowing.
    try:
        from src.services.trials import active_grant_for

        if await active_grant_for(getattr(user, "email_id", "") or "", session):
            return MediaDecision(allowed=True, cost=cost, reason="trial")
    except Exception as e:      # noqa: BLE001
        tu.logger.error(f"[MEDIA_ACCESS] trial lookup failed: {e}")

    # Anyone who bought a plan keeps the media it included. The plans are being
    # withdrawn from sale, not taken away from the people who paid.
    if getattr(user, "plan_type", None) not in (None, PlanType.FREE):
        return MediaDecision(allowed=True, cost=cost, reason="legacy_plan")

    balance = await C.get_balance(user.id, session)
    if balance >= cost:
        return MediaDecision(
            allowed=True, cost=cost, reason="credits",
            balance=balance, charge=True,
        )

    return MediaDecision(
        allowed=False, cost=cost, reason="insufficient", balance=balance,
    )
