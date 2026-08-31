"""
credits.py — the credit wallet and its ledger.

WHAT A CREDIT IS
----------------
One credit buys five minutes of generated audio or video.

    5 min = 1 credit · 10 min = 2 · 15 min = 3 · 20 min = 4

That unit is chosen from measured cost, not convenience. Media cost is
dominated by text-to-speech, which is billed per minute of audio produced, so a
twenty-minute meditation costs four times a five-minute one. "One credit per
video" would have lost money on the long one and overcharged the short one by
four times.

Audio and video cost the same per minute — video draws its imagery from the
library rather than generating any — so they cost the same in credits. Charging
more for video would not reflect anything real.

Contemplation cards are FREE and are not priced here. They use a repository
image, so a card costs a fraction of a rupee; metering it would cost more in
goodwill than it could ever recover.

HOW THE MONEY IS KEPT HONEST
----------------------------
Three database constraints, not three careful call sites:

  CHECK (balance >= 0)              a negative balance is unrepresentable
  UNIQUE (content_generation_id, kind)   one debit and one refund per generation
  UNIQUE (provider, provider_event_id)   a replayed webhook cannot pay twice

The debit is a single conditional UPDATE, so two concurrent requests cannot both
pass a balance check — there is no check to pass, only an update that either
matches a row or does not.

Every movement writes a ledger row. A refund is a REFUND row, never a silent
addition to the balance: "it went back up" is not an answer to "why".
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import CreditTransaction, CreditWallet
from src.llm_shim import tu

# ── The credit unit ──────────────────────────────────────────────────────────

MINUTES_PER_CREDIT = 5


def credits_for_minutes(minutes: int) -> int:
    """Credits needed for a piece of media of this length.

    Rounds UP, so a 6-minute request costs 2 credits rather than 1. Partial
    minutes still cost us real money.
    """
    if minutes <= 0:
        return 0
    return -(-int(minutes) // MINUTES_PER_CREDIT)   # ceiling division


def _as_uuid(value) -> Optional[UUID]:
    """Accept a UUID or its string form, store a UUID.

    The id columns are UUID-typed. Handing them a string works on Postgres by
    coercion and fails on other backends, so normalise once here rather than
    hoping every call site passes the right thing.
    """
    if value is None:
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


# ── Ledger kinds ─────────────────────────────────────────────────────────────

KIND_PURCHASE = "PURCHASE"
KIND_MEDIA_DEBIT = "MEDIA_DEBIT"
KIND_REFUND = "REFUND"
KIND_PROMOTIONAL = "PROMOTIONAL"
KIND_PATRON_MONTHLY = "PATRON_MONTHLY"
KIND_ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"


# ── Feature flag ─────────────────────────────────────────────────────────────
# off    — today's system. Wallet tables exist and are ignored.
# shadow — the wallet is written, but the OLD plan quotas still decide access.
#          This is what lets the ledger be proven against real traffic before
#          anyone's experience depends on it.
# on     — credits decide.
def credits_mode() -> str:
    return (os.getenv("ASAM_CREDITS_MODE", "off") or "off").strip().lower()


@dataclass(frozen=True)
class DebitResult:
    ok: bool
    balance: int
    charged: int
    reason: Optional[str] = None


# ── Wallet ───────────────────────────────────────────────────────────────────

async def get_or_create_wallet(user_id, session: AsyncSession) -> CreditWallet:
    wallet = (await session.execute(
        select(CreditWallet).where(CreditWallet.user_id == user_id)
    )).scalar_one_or_none()
    if wallet is not None:
        return wallet

    wallet = CreditWallet(user_id=user_id, balance=0)
    session.add(wallet)
    try:
        await session.commit()
    except IntegrityError:
        # Two requests created the wallet at once; the unique constraint on
        # user_id settled it. Take whichever won.
        await session.rollback()
        wallet = (await session.execute(
            select(CreditWallet).where(CreditWallet.user_id == user_id)
        )).scalar_one()
    await session.refresh(wallet)
    return wallet


async def get_balance(user_id, session: AsyncSession) -> int:
    wallet = (await session.execute(
        select(CreditWallet).where(CreditWallet.user_id == user_id)
    )).scalar_one_or_none()
    return int(wallet.balance) if wallet else 0


# ── Debit ────────────────────────────────────────────────────────────────────

async def debit_for_generation(
    user_id,
    amount: int,
    content_generation_id,
    session: AsyncSession,
    note: str | None = None,
) -> DebitResult:
    """Spend credits on one generation. Atomic, and safe to call twice.

    The balance is decremented by a single conditional UPDATE:

        UPDATE credit_wallets SET balance = balance - :n
         WHERE user_id = :uid AND balance >= :n

    There is no read-then-write, so two requests arriving together cannot both
    observe a sufficient balance and both spend it. If no row matches, the
    seeker could not afford it and nothing happened.

    Calling this twice for the same generation — a double-clicked Generate, a
    retried request — writes one ledger row and fails the second on the unique
    constraint, at which point the balance change is rolled back with it.
    """
    if amount <= 0:
        return DebitResult(ok=True, balance=await get_balance(user_id, session), charged=0)

    wallet = await get_or_create_wallet(user_id, session)

    # One statement, conditional on the balance. Expressed through Core rather
    # than raw SQL so the UUID binds correctly on every backend — raw text with
    # str(uuid) silently matches nothing where UUIDs are stored dash-less.
    result = await session.execute(
        update(CreditWallet)
        .where(CreditWallet.user_id == user_id, CreditWallet.balance >= amount)
        .values(balance=CreditWallet.balance - amount,
                updated_at=func.current_timestamp())
        .returning(CreditWallet.balance)
    )
    row = result.first()
    if row is None:
        await session.rollback()
        balance = await get_balance(user_id, session)
        return DebitResult(
            ok=False, balance=balance, charged=0, reason="INSUFFICIENT_CREDITS"
        )

    new_balance = int(row[0])
    session.add(CreditTransaction(
        wallet_id=wallet.id,
        delta=-amount,
        kind=KIND_MEDIA_DEBIT,
        balance_after=new_balance,
        content_generation_id=_as_uuid(content_generation_id),
        note=note,
    ))
    try:
        await session.commit()
    except IntegrityError:
        # Already debited for this generation. Roll back so the balance change
        # goes with the rejected ledger row, and report the state as it stands.
        await session.rollback()
        balance = await get_balance(user_id, session)
        tu.logger.info(
            f"[CREDITS] duplicate debit refused for generation "
            f"{content_generation_id}; balance unchanged at {balance}"
        )
        return DebitResult(ok=True, balance=balance, charged=0, reason="ALREADY_DEBITED")

    return DebitResult(ok=True, balance=new_balance, charged=amount)


# ── Refund ───────────────────────────────────────────────────────────────────

async def refund_for_generation(
    content_generation_id,
    session: AsyncSession,
    note: str | None = None,
) -> bool:
    """Return the credits spent on a generation that failed.

    Finds the original debit rather than trusting a caller-supplied amount, so
    a refund can never exceed what was taken. Safe to call more than once: the
    second attempt fails the unique constraint on (generation, REFUND) and
    leaves the balance alone.
    """
    debit = (await session.execute(
        select(CreditTransaction).where(
            CreditTransaction.content_generation_id == _as_uuid(content_generation_id),
            CreditTransaction.kind == KIND_MEDIA_DEBIT,
        )
    )).scalar_one_or_none()

    if debit is None:
        return False               # nothing was charged; nothing to give back
    amount = -int(debit.delta)
    if amount <= 0:
        return False

    result = await session.execute(
        update(CreditWallet)
        .where(CreditWallet.id == debit.wallet_id)
        .values(balance=CreditWallet.balance + amount,
                updated_at=func.current_timestamp())
        .returning(CreditWallet.balance)
    )
    row = result.first()
    if row is None:
        await session.rollback()
        return False

    session.add(CreditTransaction(
        wallet_id=debit.wallet_id,
        delta=amount,
        kind=KIND_REFUND,
        balance_after=int(row[0]),
        content_generation_id=_as_uuid(content_generation_id),
        note=note or "Generation failed",
    ))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        tu.logger.info(
            f"[CREDITS] duplicate refund refused for generation "
            f"{content_generation_id}"
        )
        return False

    tu.logger.info(
        f"[CREDITS] refunded {amount} credit(s) for failed generation "
        f"{content_generation_id}"
    )
    return True


# ── Grants that are not purchases ────────────────────────────────────────────

async def grant_credits(
    user_id,
    amount: int,
    kind: str,
    session: AsyncSession,
    note: str | None = None,
    purchase_id=None,
) -> int:
    """Add credits from a purchase, a patron allocation or an adjustment.

    Purchases must establish idempotency BEFORE calling this, by inserting the
    credit_purchases row whose unique (provider, provider_event_id) constraint
    is what makes a replayed webhook harmless. This function is the ledger
    write, not the guard.
    """
    if amount <= 0:
        return await get_balance(user_id, session)

    wallet = await get_or_create_wallet(user_id, session)
    row = (await session.execute(
        update(CreditWallet)
        .where(CreditWallet.id == wallet.id)
        .values(balance=CreditWallet.balance + amount,
                updated_at=func.current_timestamp())
        .returning(CreditWallet.balance)
    )).first()
    new_balance = int(row[0])

    session.add(CreditTransaction(
        wallet_id=wallet.id,
        delta=amount,
        kind=kind,
        balance_after=new_balance,
        purchase_id=_as_uuid(purchase_id),
        note=note,
    ))
    await session.commit()
    return new_balance


# ── Reconciliation ───────────────────────────────────────────────────────────

async def reconcile(session: AsyncSession) -> list[dict]:
    """Every wallet whose balance disagrees with its ledger.

    The materialised balance is an optimisation, and an optimisation that can
    silently diverge from the truth is a liability. This is how we find out
    from a check rather than from someone's complaint.
    """
    rows = (await session.execute(text("""
        SELECT w.id, w.user_id, w.balance,
               COALESCE(SUM(t.delta), 0) AS ledger_total
          FROM credit_wallets w
          LEFT JOIN credit_transactions t ON t.wallet_id = w.id
         GROUP BY w.id, w.user_id, w.balance
        HAVING w.balance <> COALESCE(SUM(t.delta), 0)
    """))).all()
    return [
        {
            "wallet_id": str(r[0]),
            "user_id": str(r[1]),
            "balance": int(r[2]),
            "ledger_total": int(r[3]),
            "drift": int(r[2]) - int(r[3]),
        }
        for r in rows
    ]
