"""
trials.py — time-boxed free access for named email addresses.

WHAT THIS IS FOR
----------------
Giving a specific person full run of the site for a fixed period so they can
try it or test it, without taking their money and without permanently changing
what their account is. Reviewers, the people at the Foundation, a friend asked
to look at the meditation pipeline before it goes out.

HOW IT WORKS
------------
A grant is a row saying "this email has everything until this date". The check
sits in get_usage, which is the single place every quota decision in the
product is made: conversations, contemplation cards, audio and video
meditations all read from it. Granting access therefore does not require
touching the plans table, issuing a fake subscription, or editing anything on
the user's account, and when the grant lapses the account simply goes back to
whatever it was before. Nothing has to be undone.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not create a Subscription row. A trial that looks like a paid
subscription would flow into revenue figures, into the Polar and Razorpay
reconciliation, and into any "how many subscribers do we have" question asked
later. Free access and paid access should not be the same record.

It does not grant admin. A trial user should see the product as a paying
seeker sees it, not the admin console.
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import TrialGrant, UserProfile, get_db_session_fa
from src.dependencies import get_current_user

# A grant has to end. An open-ended one is just a free account nobody
# remembers creating, so the length is capped and the cap is explicit.
MAX_TRIAL_DAYS = 365
DEFAULT_TRIAL_DAYS = 30


def normalise_email(email: str) -> str:
    """Lower-cased and trimmed.

    Every lookup and every write goes through this. Without it a grant written
    as "Someone@Gmail.com " silently fails to match the account that signed up
    as "someone@gmail.com", and the failure looks like the feature is broken
    rather than like a typo.
    """
    return (email or "").strip().lower()


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


async def active_grant_for(
    email: str, session: AsyncSession
) -> Optional[TrialGrant]:
    """The live grant for this email, or None.

    Live means: not revoked, already started, not yet expired. If somebody has
    been granted access more than once, the one that runs longest wins, so a
    later extension does not get shadowed by an earlier short grant.
    """
    address = normalise_email(email)
    if not address:
        return None

    now = _now()
    rows = (await session.execute(
        select(TrialGrant)
        .where(
            TrialGrant.email == address,
            TrialGrant.revoked_at.is_(None),
            TrialGrant.starts_at <= now,
            TrialGrant.expires_at > now,
        )
        .order_by(TrialGrant.expires_at.desc())
        .limit(1)
    )).scalars().all()
    return rows[0] if rows else None


# ── Admin API ────────────────────────────────────────────────────────────────

async def list_trial_grants(
    session: AsyncSession = Depends(get_db_session_fa),
):
    """GET /api/admin/trials — every grant, newest first, with live status."""
    rows = (await session.execute(
        select(TrialGrant).order_by(TrialGrant.created_at.desc())
    )).scalars().all()

    now = _now()
    out = []
    for g in rows:
        if g.revoked_at is not None:
            status = "revoked"
        elif g.expires_at <= now:
            status = "expired"
        elif g.starts_at > now:
            status = "scheduled"
        else:
            status = "active"
        out.append({
            "id": str(g.id),
            "email": g.email,
            "status": status,
            "starts_at": g.starts_at.isoformat(),
            "expires_at": g.expires_at.isoformat(),
            "days_left": max(0, (g.expires_at - now).days) if status == "active" else 0,
            "note": g.note,
            "granted_by": g.granted_by,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        })
    return {"grants": out, "active": sum(1 for g in out if g["status"] == "active")}


async def create_trial_grant(
    payload: dict,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
):
    """POST /api/admin/trials — give an email full access for a period.

    Accepts {email, days} or {email, expires_at}. Granting the same address
    again does not stack: the existing live grant is replaced, so "extend Ravi
    by another month" behaves the way it reads rather than leaving two
    overlapping rows whose combined effect nobody can see.
    """
    email = normalise_email(payload.get("email", ""))
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required.")

    now = _now()
    expires_raw = payload.get("expires_at")
    if expires_raw:
        try:
            expires_at = _dt.datetime.fromisoformat(
                str(expires_raw).replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="expires_at must be an ISO date, for example 2026-12-31.",
            )
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=_dt.timezone.utc)
    else:
        try:
            days = int(payload.get("days", DEFAULT_TRIAL_DAYS))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="days must be a number.")
        if days < 1:
            raise HTTPException(status_code=400, detail="days must be at least 1.")
        if days > MAX_TRIAL_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"A trial cannot run longer than {MAX_TRIAL_DAYS} days.",
            )
        expires_at = now + _dt.timedelta(days=days)

    if expires_at <= now:
        raise HTTPException(status_code=400, detail="That date is in the past.")
    if expires_at > now + _dt.timedelta(days=MAX_TRIAL_DAYS):
        raise HTTPException(
            status_code=400,
            detail=f"A trial cannot run longer than {MAX_TRIAL_DAYS} days.",
        )

    # Supersede any live grant for the same address rather than stacking.
    existing = (await session.execute(
        select(TrialGrant).where(
            TrialGrant.email == email,
            TrialGrant.revoked_at.is_(None),
            TrialGrant.expires_at > now,
        )
    )).scalars().all()
    for g in existing:
        g.revoked_at = now

    grant = TrialGrant(
        email=email,
        starts_at=now,
        expires_at=expires_at,
        note=(payload.get("note") or None),
        granted_by=getattr(current_user, "email_id", None),
    )
    session.add(grant)
    await session.commit()
    await session.refresh(grant)

    return {
        "success": True,
        "id": str(grant.id),
        "email": grant.email,
        "expires_at": grant.expires_at.isoformat(),
        "replaced": len(existing),
        "message": (
            f"{grant.email} has full access until "
            f"{grant.expires_at.strftime('%d %b %Y')}."
        ),
    }


async def revoke_trial_grant(
    grant_id: UUID,
    session: AsyncSession = Depends(get_db_session_fa),
):
    """DELETE /api/admin/trials/{id} — end a grant now.

    Marks it revoked rather than deleting the row, so the record of who was
    given free access survives the revocation.
    """
    grant = (await session.execute(
        select(TrialGrant).where(TrialGrant.id == grant_id)
    )).scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=404, detail="No such grant.")
    if grant.revoked_at is None:
        grant.revoked_at = _now()
        await session.commit()
    return {"success": True, "id": str(grant_id), "email": grant.email}


async def my_trial_status(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
):
    """GET /api/trial-status — so the UI can tell the person what they have.

    Someone on a trial should know it is a trial and when it ends, rather than
    discovering the date by being cut off.
    """
    grant = await active_grant_for(
        getattr(current_user, "email_id", ""), session
    )
    if grant is None:
        return {"on_trial": False}
    return {
        "on_trial": True,
        "expires_at": grant.expires_at.isoformat(),
        "days_left": max(0, (grant.expires_at - _now()).days),
    }
