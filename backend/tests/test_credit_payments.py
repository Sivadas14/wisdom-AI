"""Tests for src/services/credit_payments.py — how money becomes credits.

The single property that matters most: THE SAME PAYMENT CAN ONLY EVER PAY
ONCE, however many times we hear about it. Razorpay delivers a success handler
AND a webhook for one payment; Polar delivers checkout.created AND
order.created for one purchase; any webhook can be redelivered. Every one of
those paths funnels through record_and_grant, whose insert into
credit_purchases is gated by UNIQUE (provider, provider_event_id).

Real models, real constraints, real database — the same discipline as
test_credits.py, and for the same reason: a mock would accept the double
grant these tests exist to rule out.
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.db import Base, CreditPurchase, CreditTransaction, CreditWallet  # noqa: E402
from src.services import credits as C  # noqa: E402
from src.services.credit_payments import (  # noqa: E402
    PACKS, pack_catalogue, polar_credit_purchase, record_and_grant,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[CreditWallet.__table__, CreditTransaction.__table__,
                    CreditPurchase.__table__],
        )
    return async_sessionmaker(engine, expire_on_commit=False)


# ── The catalogue ────────────────────────────────────────────────────────────

def test_the_packs_match_the_approved_economics():
    """Phase 2 as approved: 4/12/30 credits at Rs149/399/899 and $5/12/25."""
    assert (PACKS["small"].credits, PACKS["small"].inr_paise, PACKS["small"].usd_cents) == (4, 14900, 500)
    assert (PACKS["standard"].credits, PACKS["standard"].inr_paise, PACKS["standard"].usd_cents) == (12, 39900, 1200)
    assert (PACKS["supporter"].credits, PACKS["supporter"].inr_paise, PACKS["supporter"].usd_cents) == (30, 89900, 2500)


def test_the_catalogue_states_minutes_not_just_credits():
    """The buyer is buying minutes of meditation; the catalogue must say so."""
    for row in pack_catalogue():
        assert row["minutes"] == row["credits"] * 5, row


# ── One payment pays once ────────────────────────────────────────────────────

def test_a_purchase_credits_the_wallet():
    async def go():
        f = await _db()
        uid = uuid.uuid4()
        async with f() as s:
            r = await record_and_grant(
                s, uid, "razorpay", "pay_001", PACKS["standard"], 39900, "INR")
            assert r["status"] == "credited" and r["balance"] == 12, r
    run(go())


def test_the_same_payment_heard_twice_pays_once():
    """Success handler AND webhook both report payment pay_002. One grant."""
    async def go():
        f = await _db()
        uid = uuid.uuid4()
        async with f() as s:
            first = await record_and_grant(
                s, uid, "razorpay", "pay_002", PACKS["small"], 14900, "INR")
        async with f() as s:
            second = await record_and_grant(
                s, uid, "razorpay", "pay_002", PACKS["small"], 14900, "INR")
            assert first["status"] == "credited"
            assert second["status"] == "already_processed", second
            assert await C.get_balance(uid, s) == 4
    run(go())


def test_polars_two_events_for_one_checkout_pay_once():
    """The bug in the add-on path, made impossible here. checkout.created and
    order.created for the same purchase share the checkout id, so the second
    one is a recorded no-op."""
    async def go():
        f = await _db()
        uid = str(uuid.uuid4())
        checkout_evt = {
            "type": "checkout.created",
            "data": {"id": "chk_77", "status": "succeeded",
                     "metadata": {"type": "credit_pack", "pack_key": "standard",
                                  "user_id": uid}},
        }
        order_evt = {
            "type": "order.created",
            "data": {"id": "ord_99", "checkout_id": "chk_77",
                     "metadata": {"type": "credit_pack", "pack_key": "standard",
                                  "user_id": uid}},
        }
        async with f() as s:
            r1 = await polar_credit_purchase(s, checkout_evt)
        async with f() as s:
            r2 = await polar_credit_purchase(s, order_evt)
            assert r1["status"] == "credited", r1
            assert r2["status"] == "already_processed", r2
            assert await C.get_balance(uuid.UUID(uid), s) == 12
    run(go())


def test_an_unsucceeded_checkout_pays_nothing():
    async def go():
        f = await _db()
        uid = str(uuid.uuid4())
        evt = {"type": "checkout.created",
               "data": {"id": "chk_open", "status": "open",
                        "metadata": {"type": "credit_pack", "pack_key": "small",
                                     "user_id": uid}}}
        async with f() as s:
            r = await polar_credit_purchase(s, evt)
            assert r["status"] == "ignored", r
            assert await C.get_balance(uuid.UUID(uid), s) == 0
    run(go())


def test_missing_metadata_is_ignored_not_crashed():
    async def go():
        f = await _db()
        async with f() as s:
            for evt in [
                {"type": "order.created", "data": {}},
                {"type": "order.created", "data": {"id": "x", "metadata": {}}},
                {"type": "order.created",
                 "data": {"id": "x", "metadata": {"type": "credit_pack",
                                                  "pack_key": "nonsense",
                                                  "user_id": "u"}}},
            ]:
                r = await polar_credit_purchase(s, evt)
                assert r["status"] == "ignored", (evt, r)
    run(go())


def test_two_genuinely_different_payments_both_pay():
    async def go():
        f = await _db()
        uid = uuid.uuid4()
        async with f() as s:
            await record_and_grant(s, uid, "razorpay", "pay_a", PACKS["small"], 14900, "INR")
            await record_and_grant(s, uid, "razorpay", "pay_b", PACKS["small"], 14900, "INR")
            assert await C.get_balance(uid, s) == 8
    run(go())


def test_the_ledger_links_the_purchase():
    """Every PURCHASE row must point at its credit_purchases record, so a
    credit can always be traced back to the money that bought it."""
    async def go():
        f = await _db()
        uid = uuid.uuid4()
        async with f() as s:
            await record_and_grant(s, uid, "polar", "chk_1", PACKS["supporter"], 2500, "USD")
        async with f() as s:
            from sqlalchemy import select
            txn = (await s.execute(
                select(CreditTransaction).where(CreditTransaction.kind == C.KIND_PURCHASE)
            )).scalar_one()
            assert txn.purchase_id is not None
            purchase = (await s.execute(
                select(CreditPurchase).where(CreditPurchase.id == txn.purchase_id)
            )).scalar_one()
            assert purchase.provider_event_id == "chk_1"
            assert purchase.credits == 30
    run(go())


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"PASS  {name}"); passed += 1
            except AssertionError as e:
                print(f"FAIL  {name}: {e}"); failed += 1
            except Exception as e:
                print(f"ERROR {name}: {type(e).__name__}: {e}"); failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
