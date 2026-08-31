"""
credit_payments.py — buying credit packs.

TWO PROVIDERS, ONE RULE
-----------------------
India pays in rupees through Razorpay; everyone else pays in dollars through
Polar. Both arrive here, and both are made idempotent the same way: the
purchase is recorded in credit_purchases BEFORE any credits move, and that
table's UNIQUE (provider, provider_event_id) means the same payment can only
ever be recorded once. Credits are granted only when that insert succeeds.
A replayed webhook, a double-fired success handler, a verify endpoint raced
against a webhook — all collapse into one purchase.

This is the guard the existing add-on path lacks. pollor_service accepts both
checkout.created and order.created for one purchase and credits each of them.
Nothing from that module is reused here.

WHY RAZORPAY ORDERS, NOT SUBSCRIPTIONS
--------------------------------------
The existing razorpay_service only creates subscriptions — recurring mandates,
with their own approval flow and their own webhooks. A credit pack is a single
payment. Razorpay's Orders API is the right shape: create an order, the
Checkout JS collects payment against it, and the signature formula is
HMAC(order_id|payment_id) rather than the subscription form.

THE PACKS
---------
Sized from the Phase 2 economics (58-76% contribution after fees at these
prices, which is what carries free chat and the fixed infrastructure floor):

    India (Razorpay):   4 cr Rs149 · 12 cr Rs399 · 30 cr Rs899
    Intl  (Polar):      4 cr $5    · 12 cr $12   · 30 cr $25

No crossed-out prices, no timers, no scarcity. Larger packs are modestly
cheaper per credit and nothing more.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import CreditPurchase, UserProfile, get_db_session_fa
from src.dependencies import get_current_user
from src.llm_shim import tu
from src.services import credits as C
from src.settings import get_settings


@dataclass(frozen=True)
class Pack:
    key: str
    credits: int
    inr_paise: int
    usd_cents: int
    label: str


PACKS: dict[str, Pack] = {
    "small":     Pack("small",     4,  14900,  500, "Small — 4 credits (20 minutes)"),
    "standard":  Pack("standard", 12,  39900, 1200, "Standard — 12 credits (60 minutes)"),
    "supporter": Pack("supporter", 30, 89900, 2500, "Supporter — 30 credits (150 minutes)"),
}


def pack_catalogue() -> list[dict]:
    return [
        {
            "key": p.key,
            "label": p.label,
            "credits": p.credits,
            "minutes": p.credits * C.MINUTES_PER_CREDIT,
            "price_inr": p.inr_paise / 100,
            "price_usd": p.usd_cents / 100,
        }
        for p in PACKS.values()
    ]


# ── The one idempotent path to credits ───────────────────────────────────────

async def record_and_grant(
    session: AsyncSession,
    user_id,
    provider: str,
    provider_event_id: str,
    pack: Pack,
    amount_minor: int,
    currency: str,
) -> dict:
    """Record the purchase, then grant the credits. In that order, always.

    The insert into credit_purchases is the idempotency gate: its unique
    (provider, provider_event_id) makes the second recording of the same
    payment fail cleanly, and credits are only granted when the insert
    succeeded. There is deliberately no "check if exists then insert" —
    that pattern is exactly the race that double-credits.
    """
    # Webhooks deliver the user id as a string; the column is UUID-typed.
    # Postgres would coerce it silently, other backends reject it — the same
    # class of bug already fixed in credits.py, guarded at the boundary here.
    user_id = C._as_uuid(user_id)
    purchase = CreditPurchase(
        user_id=user_id,
        provider=provider,
        provider_event_id=provider_event_id,
        pack_key=pack.key,
        credits=pack.credits,
        amount_minor=amount_minor,
        currency=currency,
        status="paid",
    )
    session.add(purchase)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        tu.logger.info(
            f"[CREDITS] duplicate payment event ignored: {provider} "
            f"{provider_event_id}"
        )
        balance = await C.get_balance(user_id, session)
        return {"status": "already_processed", "balance": balance}

    await session.refresh(purchase)
    balance = await C.grant_credits(
        user_id, pack.credits, C.KIND_PURCHASE, session,
        note=f"{pack.label}", purchase_id=purchase.id,
    )
    tu.logger.info(
        f"[CREDITS] purchase {purchase.id}: {pack.credits} credits to "
        f"{user_id} via {provider} ({provider_event_id}); balance {balance}"
    )
    return {"status": "credited", "credits": pack.credits, "balance": balance}


# ── Wallet view ──────────────────────────────────────────────────────────────

async def get_credits(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
):
    """GET /api/credits — balance, recent ledger, and the pack catalogue."""
    from src.db import CreditTransaction, CreditWallet

    balance = await C.get_balance(current_user.id, session)
    wallet = (await session.execute(
        select(CreditWallet).where(CreditWallet.user_id == current_user.id)
    )).scalar_one_or_none()

    ledger = []
    if wallet:
        rows = (await session.execute(
            select(CreditTransaction)
            .where(CreditTransaction.wallet_id == wallet.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(50)
        )).scalars().all()
        ledger = [
            {
                "delta": t.delta,
                "kind": t.kind,
                "balance_after": t.balance_after,
                "note": t.note,
                "at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in rows
        ]

    return {
        "balance": balance,
        "minutes_per_credit": C.MINUTES_PER_CREDIT,
        "packs": pack_catalogue(),
        "ledger": ledger,
    }


# ── Razorpay: one-time order ─────────────────────────────────────────────────

async def create_checkout(
    payload: dict,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
):
    """POST /api/credits/checkout — {pack_key, currency: INR|USD}.

    INR returns a Razorpay order for the Checkout JS to collect against.
    USD returns a Polar checkout URL to redirect to.
    """
    pack = PACKS.get(str(payload.get("pack_key", "")).lower())
    if not pack:
        raise HTTPException(status_code=400, detail="Unknown pack.")
    currency = str(payload.get("currency", "INR")).upper()

    if currency == "INR":
        from src.razorpayservice.razorpay_client import get_razorpay_client

        client = get_razorpay_client()
        order = client.order.create({
            "amount": pack.inr_paise,
            "currency": "INR",
            "notes": {
                # The webhook reads these to know who bought what. user_id is
                # ours, not client-supplied: the payment can only credit the
                # account that opened the checkout.
                "type": "credit_pack",
                "user_id": str(current_user.id),
                "pack_key": pack.key,
            },
        })
        return {
            "provider": "razorpay",
            "order_id": order["id"],
            "amount": pack.inr_paise,
            "currency": "INR",
            "key_id": get_settings().razorpay_key_id,
            "pack": pack.key,
        }

    if currency == "USD":
        from src.polarservice.polar_client import get_polar_client

        with get_polar_client() as polar:
            checkout = polar.checkouts.create(request={
                "products": [_polar_product_for(pack)],
                "customer_email": getattr(current_user, "email_id", None),
                "success_url": f"{get_settings().frontend_url}/credits?purchase=success",
                "metadata": {
                    "type": "credit_pack",
                    "user_id": str(current_user.id),
                    "pack_key": pack.key,
                },
            })
        return {"provider": "polar", "checkout_url": checkout.url, "pack": pack.key}

    raise HTTPException(status_code=400, detail="currency must be INR or USD.")


def _polar_product_for(pack: Pack) -> str:
    """The Polar product id for a pack, from environment configuration.

    UNKNOWN — MUST BE CONFIGURED: the three products have to be created in the
    Polar dashboard and their ids set as ASAM_POLAR_PACK_SMALL / _STANDARD /
    _SUPPORTER. Failing loudly here beats a checkout for the wrong product.
    """
    import os

    env_key = f"ASAM_POLAR_PACK_{pack.key.upper()}"
    product_id = os.getenv(env_key, "").strip()
    if not product_id:
        raise HTTPException(
            status_code=503,
            detail=f"International checkout is not configured ({env_key} unset).",
        )
    return product_id


async def verify_razorpay_payment(
    payload: dict,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
):
    """POST /api/credits/razorpay-verify — the Checkout JS success handler.

    Signature formula for ORDERS (not the subscription formula):
        HMAC_SHA256(order_id + "|" + payment_id, key_secret)

    Credits on the PAYMENT id, the same id the webhook uses, so whichever of
    the two arrives second is a recorded no-op rather than a second grant.
    """
    order_id = str(payload.get("razorpay_order_id", ""))
    payment_id = str(payload.get("razorpay_payment_id", ""))
    signature = str(payload.get("razorpay_signature", ""))
    pack = PACKS.get(str(payload.get("pack_key", "")).lower())
    if not (order_id and payment_id and signature and pack):
        raise HTTPException(status_code=400, detail="Missing payment fields.")

    secret = get_settings().razorpay_key_secret or ""
    if not secret:
        raise HTTPException(status_code=503, detail="Payments not configured.")
    expected = hmac.new(
        secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        tu.logger.error(f"[CREDITS] bad Razorpay signature for order {order_id}")
        raise HTTPException(status_code=400, detail="Signature verification failed.")

    return await record_and_grant(
        session, current_user.id, "razorpay", payment_id,
        pack, pack.inr_paise, "INR",
    )


async def razorpay_webhook(request, session: AsyncSession):
    """payment.captured for credit-pack orders. Registered by server.py with
    the raw request so the body can be signature-checked before parsing."""
    import json

    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = get_settings().razorpay_webhook_secret or ""
    if not secret:
        # Refuse rather than trust: an unverifiable webhook that grants money
        # must not be allowed to fail open the way the Polar path does.
        tu.logger.error("[CREDITS] razorpay webhook secret unset; rejecting")
        raise HTTPException(status_code=503, detail="Webhook not configured.")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    event = json.loads(body)
    if event.get("event") != "payment.captured":
        return {"status": "ignored"}

    payment = (event.get("payload", {}).get("payment", {}).get("entity", {}))
    notes = payment.get("notes", {}) or {}
    if notes.get("type") != "credit_pack":
        return {"status": "ignored"}          # a subscription payment; not ours

    pack = PACKS.get(str(notes.get("pack_key", "")).lower())
    user_id = notes.get("user_id")
    if not pack or not user_id:
        tu.logger.error(f"[CREDITS] credit_pack webhook missing notes: {notes}")
        return {"status": "ignored"}

    return await record_and_grant(
        session, user_id, "razorpay", payment.get("id", ""),
        pack, int(payment.get("amount", pack.inr_paise)), "INR",
    )


async def polar_credit_purchase(session: AsyncSession, payload: dict) -> dict:
    """Called from the existing Polar webhook route when metadata says
    type=credit_pack. Polar sends checkout.created AND order.created for one
    purchase; keying on the CHECKOUT id, which both events carry, makes the
    pair collapse into one grant.
    """
    data = payload.get("data", {}) or {}
    metadata = data.get("metadata", {}) or {}
    pack = PACKS.get(str(metadata.get("pack_key", "")).lower())
    user_id = metadata.get("user_id")
    if not pack or not user_id:
        return {"status": "ignored", "reason": "missing_metadata"}

    event_type = payload.get("type", "")
    if event_type == "checkout.created" and data.get("status") != "succeeded":
        return {"status": "ignored", "reason": "not_succeeded"}
    if event_type not in ("checkout.created", "order.created"):
        return {"status": "ignored", "reason": "event_type"}

    # order.created carries the originating checkout id; checkout.created IS
    # the checkout. One id for both, therefore one purchase row for both.
    event_id = (
        data.get("checkout_id") or data.get("id") or ""
    )
    if not event_id:
        return {"status": "ignored", "reason": "no_event_id"}

    return await record_and_grant(
        session, user_id, "polar", str(event_id),
        pack, pack.usd_cents, "USD",
    )


# ── Admin: grant and self-test ───────────────────────────────────────────────

async def admin_grant_credits(
    payload: dict,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
):
    """POST /api/admin/credits/grant — {email, credits, note}.

    The operational lever: a support adjustment, a promotional gift, topping
    up a tester. Written to the ledger as ADMIN_ADJUSTMENT with who did it,
    because credits that appear without a paper trail are exactly what the
    ledger exists to prevent.
    """
    from src.db import UserProfile as UP

    email = str(payload.get("email", "")).strip().lower()
    try:
        amount = int(payload.get("credits", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="credits must be a number.")
    if not email or amount == 0:
        raise HTTPException(status_code=400, detail="email and a non-zero credits amount are required.")
    if abs(amount) > 500:
        raise HTTPException(status_code=400, detail="That is a lot of credits for one adjustment. Do it in steps if you mean it.")

    target = (await session.execute(
        select(UP).where(UP.email_id == email)
    )).scalars().first()
    if target is None:
        raise HTTPException(status_code=404, detail=f"No account with email {email}.")

    note = f"{payload.get('note') or 'Admin adjustment'} (by {getattr(current_user, 'email_id', 'admin')})"
    if amount > 0:
        balance = await C.grant_credits(target.id, amount, C.KIND_ADMIN_ADJUSTMENT, session, note=note)
    else:
        # A negative adjustment goes through the same conditional debit so it
        # can never push a balance below zero.
        import uuid as _uuid
        result = await C.debit_for_generation(target.id, -amount, _uuid.uuid4(), session, note=note)
        if not result.ok:
            raise HTTPException(status_code=400, detail=f"Balance is {result.balance}; cannot remove {-amount}.")
        balance = result.balance
    return {"success": True, "email": email, "balance": balance}


async def admin_credits_selftest(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
):
    """POST /api/admin/credits/selftest — prove the money on THIS database.

    The unit tests prove the logic on SQLite, which serialises writers, so
    they cannot prove the conditional UPDATE under real Postgres concurrency.
    This runs the whole dangerous set against the calling admin's own wallet —
    grant, concurrent double debit, over-spend, refund, double refund — and
    reverses everything, reporting each expectation. Run it after any deploy
    that touches the credit path; a failure here is a failure that would
    otherwise be found by a paying seeker.
    """
    import asyncio as _asyncio
    import uuid as _uuid

    from src.db import get_background_session

    uid = current_user.id
    results = []

    def check(name, ok, detail=""):
        results.append({"check": name, "ok": bool(ok), "detail": str(detail)})

    start_balance = await C.get_balance(uid, session)

    # 1. Grant 3.
    bal = await C.grant_credits(uid, 3, C.KIND_ADMIN_ADJUSTMENT, session, note="selftest grant")
    check("grant_3", bal == start_balance + 3, f"balance {bal}")

    # 2. TWO CONCURRENT debits of the same generation, each on its OWN session
    #    — the real race, on the real database. Exactly one may charge.
    gen = _uuid.uuid4()

    async def _debit():
        async with get_background_session() as s:
            return await C.debit_for_generation(uid, 1, gen, s, note="selftest concurrent")

    a, b = await _asyncio.gather(_debit(), _debit())
    charged = (a.charged or 0) + (b.charged or 0)
    check("concurrent_double_debit_charges_once", charged == 1,
          f"charged {a.charged}+{b.charged}")

    # 3. Over-spend: try to take far more than the balance holds.
    big = await C.debit_for_generation(uid, 9999, _uuid.uuid4(), session, note="selftest overdraft")
    check("overdraft_refused", not big.ok and big.reason == "INSUFFICIENT_CREDITS", big.reason)

    # 4. Refund the concurrent debit; balance returns.
    refunded = await C.refund_for_generation(gen, session, note="selftest refund")
    check("refund_returns_credit", refunded is True)

    # 5. Refund again; nothing moves.
    again = await C.refund_for_generation(gen, session, note="selftest refund again")
    check("double_refund_refused", again is False)

    # 6. Reverse the grant, leaving the wallet exactly as found.
    result = await C.debit_for_generation(uid, 3, _uuid.uuid4(), session, note="selftest cleanup")
    end_balance = await C.get_balance(uid, session)
    check("wallet_restored", end_balance == start_balance,
          f"start {start_balance}, end {end_balance}")

    # 7. Ledger and balance agree for every wallet in the system.
    drift = await C.reconcile(session)
    check("no_ledger_drift", drift == [], drift)

    passed = sum(1 for r in results if r["ok"])
    return {"passed": passed, "failed": len(results) - passed, "results": results}
