"""
Referral arrivals — who sent us a visitor, and how many.

The first (and for now only) source is the AstroPal footer link, which arrives
as `?from=astropal`. The question this exists to answer is narrow and honest:
is that link worth keeping? Without a number, the answer in six months is a
shrug, and a link nobody can evaluate stays forever by default.

Two deliberate choices:

  · Recorded server-side, as the page is served. A browser beacon would miss
    the visitor who reads the landing page and leaves — but that visitor did
    click the link, and the click is the thing being measured. It is also the
    first thing an ad blocker drops.

  · The IP is hashed (SHA-256) and never stored raw, matching what
    guest_sessions already does. Its only job is to separate one curious
    person refreshing from twenty different people. It is not an identity and
    must not be allowed to become one.
"""

import hashlib
import logging

from sqlalchemy import insert

from src import db

logger = logging.getLogger(__name__)

# Obvious automated traffic. This list is deliberately short and dumb: the goal
# is to strip the crawlers that would otherwise make a dead link look alive,
# not to win an arms race against anything that wants to lie to us. A referral
# count inflated by Googlebot is worse than useless — it is misleading in the
# direction that flatters the decision we are trying to evaluate.
_BOT_MARKERS = (
    "bot", "crawler", "spider", "slurp", "curl", "wget", "python-requests",
    "headlesschrome", "phantomjs", "lighthouse", "pingdom", "uptimerobot",
    "monitoring", "preview", "facebookexternalhit", "whatsapp", "telegram",
)


def looks_like_a_bot(user_agent: str | None) -> bool:
    """True for traffic we should not count as a human referral."""
    if not user_agent:
        # No user-agent at all is not a browser. Real browsers always send one.
        return True
    ua = user_agent.lower()
    return any(marker in ua for marker in _BOT_MARKERS)


def hash_ip(ip: str | None) -> str | None:
    """SHA-256 of the address. Never store or log the raw value."""
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


async def record_referral_hit(
    session_factory,
    source: str,
    client_ip: str | None,
    user_agent: str | None,
    path: str | None,
) -> None:
    """Write one referral row. Runs as a background task after the response.

    Every failure path here is swallowed on purpose. This function exists to
    satisfy curiosity about a footer link; nothing it does is worth degrading
    a page load, and an exception raised in a background task would be logged
    as a server error for a visitor who was served a perfectly good page.
    """
    if session_factory is None:
        return
    if looks_like_a_bot(user_agent):
        return

    try:
        async with session_factory() as session:
            await session.execute(
                insert(db.ReferralHit).values(
                    source=source,
                    ip_hash=hash_ip(client_ip),
                    path=(path or "")[:512] or None,
                )
            )
            await session.commit()
    except Exception as exc:
        # Deliberately debug, not error: a missing referral row is a rounding
        # error in a vanity metric. Logging it at error level would train
        # whoever reads the logs to ignore real problems.
        logger.debug("Could not record referral hit (%s): %s", source, exc)
