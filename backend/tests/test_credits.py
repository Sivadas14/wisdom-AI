"""Tests for src/services/credits.py — the money.

These run the REAL SQLAlchemy models against a real database (SQLite in
memory), not mocks. That matters here more than anywhere else in the codebase,
because the safety properties are enforced by database constraints rather than
by application code:

    CHECK (balance >= 0)
    UNIQUE (content_generation_id, kind)
    UNIQUE (provider, provider_event_id)

A mocked session would happily accept a double debit and prove nothing. The
point of these tests is to demonstrate that the database refuses it.

What is NOT covered here, and must be checked on Postgres before the flag is
turned on: true row-level concurrency. SQLite serialises writers, so the
"two simultaneous debits" test below proves the logic and the constraint, not
the locking. The conditional UPDATE is what makes it safe on Postgres, and
that is exercised in staging.
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.db import Base, CreditPurchase, CreditTransaction, CreditWallet  # noqa: E402
from src.services import credits as C  # noqa: E402


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _fresh_session():
    """A database with only the three credit tables, and foreign keys off.

    The credit tables reference user_profiles, which drags in the whole schema
    (pgvector included) if created. The money logic does not care whether the
    user row exists, so the tables under test are created alone.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[CreditWallet.__table__, CreditTransaction.__table__,
                    CreditPurchase.__table__],
        )
    return async_sessionmaker(engine, expire_on_commit=False)


async def _wallet_with(session_factory, balance: int):
    uid = uuid.uuid4()
    async with session_factory() as s:
        await C.get_or_create_wallet(uid, s)
        if balance:
            await C.grant_credits(uid, balance, C.KIND_PURCHASE, s, note="test seed")
    return uid


# ── 1. The credit unit ───────────────────────────────────────────────────────

def test_five_minutes_is_one_credit():
    assert C.credits_for_minutes(5) == 1


def test_twenty_minutes_is_four_credits():
    """The whole reason the unit is minutes rather than items. A 20-minute
    video costs four times a 5-minute one to produce, so it costs four
    credits."""
    assert C.credits_for_minutes(10) == 2
    assert C.credits_for_minutes(15) == 3
    assert C.credits_for_minutes(20) == 4


def test_partial_minutes_round_up():
    """Six minutes of speech costs us more than five, so it cannot cost one."""
    assert C.credits_for_minutes(6) == 2
    assert C.credits_for_minutes(1) == 1


def test_zero_and_negative_are_free():
    assert C.credits_for_minutes(0) == 0
    assert C.credits_for_minutes(-5) == 0


# ── 2. Spending ──────────────────────────────────────────────────────────────

def test_a_successful_debit_leaves_the_right_balance():
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 3)
        async with f() as s:
            r = await C.debit_for_generation(uid, 1, uuid.uuid4(), s)
            assert r.ok and r.charged == 1, r
            assert r.balance == 2, r
    run(go())


def test_a_twenty_minute_video_costs_four():
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 6)
        async with f() as s:
            need = C.credits_for_minutes(20)
            r = await C.debit_for_generation(uid, need, uuid.uuid4(), s)
            assert r.charged == 4 and r.balance == 2, r
    run(go())


def test_insufficient_balance_is_refused_and_takes_nothing():
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 2)
        async with f() as s:
            r = await C.debit_for_generation(uid, 4, uuid.uuid4(), s)
            assert not r.ok, r
            assert r.reason == "INSUFFICIENT_CREDITS"
            assert r.charged == 0
        async with f() as s:
            assert await C.get_balance(uid, s) == 2
    run(go())


def test_zero_balance_is_refused():
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 0)
        async with f() as s:
            r = await C.debit_for_generation(uid, 1, uuid.uuid4(), s)
            assert not r.ok
            assert await C.get_balance(uid, s) == 0
    run(go())


def test_a_double_click_debits_once():
    """The same generation debited twice must take one credit, not two.

    Enforced by UNIQUE (content_generation_id, kind), so it holds however the
    second call arrives: a double-clicked button, a retried request, a
    duplicated background task.
    """
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 3)
        gen = uuid.uuid4()
        async with f() as s:
            first = await C.debit_for_generation(uid, 1, gen, s)
        async with f() as s:
            second = await C.debit_for_generation(uid, 1, gen, s)
        assert first.charged == 1
        assert second.charged == 0, second
        assert second.reason == "ALREADY_DEBITED"
        async with f() as s:
            assert await C.get_balance(uid, s) == 2
            rows = (await s.execute(
                CreditTransaction.__table__.select().where(
                    CreditTransaction.content_generation_id == gen)
            )).all()
            assert len(rows) == 1, f"expected one ledger row, got {len(rows)}"
    run(go())


def test_the_balance_can_never_go_negative():
    """Not 'is checked before' — cannot be represented. The CHECK constraint
    would reject the row even if every guard above it were removed."""
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 1)
        async with f() as s:
            for _ in range(5):
                await C.debit_for_generation(uid, 1, uuid.uuid4(), s)
        async with f() as s:
            assert await C.get_balance(uid, s) == 0
    run(go())


# ── 3. Refunds ───────────────────────────────────────────────────────────────

def test_a_failed_generation_gives_the_credit_back():
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 1)
        gen = uuid.uuid4()
        async with f() as s:
            await C.debit_for_generation(uid, 1, gen, s)
            assert await C.get_balance(uid, s) == 0
        async with f() as s:
            assert await C.refund_for_generation(gen, s) is True
            assert await C.get_balance(uid, s) == 1
    run(go())


def test_the_refund_is_recorded_not_just_reversed():
    """Per the requirement: the ledger must show a debit AND a refund. A
    balance that quietly went back up does not say why."""
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 1)
        gen = uuid.uuid4()
        async with f() as s:
            await C.debit_for_generation(uid, 1, gen, s)
        async with f() as s:
            await C.refund_for_generation(gen, s)
        async with f() as s:
            rows = (await s.execute(
                CreditTransaction.__table__.select().where(
                    CreditTransaction.content_generation_id == gen)
            )).all()
            kinds = sorted(r.kind for r in rows)
            assert kinds == [C.KIND_MEDIA_DEBIT, C.KIND_REFUND], kinds
    run(go())


def test_a_twenty_minute_failure_refunds_all_four():
    """The refund reads the original debit rather than trusting a caller, so
    it returns exactly what was taken."""
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 4)
        gen = uuid.uuid4()
        async with f() as s:
            await C.debit_for_generation(uid, 4, gen, s)
            assert await C.get_balance(uid, s) == 0
        async with f() as s:
            await C.refund_for_generation(gen, s)
            assert await C.get_balance(uid, s) == 4
    run(go())


def test_refunding_twice_does_not_pay_twice():
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 1)
        gen = uuid.uuid4()
        async with f() as s:
            await C.debit_for_generation(uid, 1, gen, s)
        async with f() as s:
            assert await C.refund_for_generation(gen, s) is True
        async with f() as s:
            assert await C.refund_for_generation(gen, s) is False
        async with f() as s:
            assert await C.get_balance(uid, s) == 1
    run(go())


def test_refunding_something_never_charged_pays_nothing():
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 2)
        async with f() as s:
            assert await C.refund_for_generation(uuid.uuid4(), s) is False
            assert await C.get_balance(uid, s) == 2
    run(go())


# ── 4. Purchases: a replayed webhook must not pay twice ──────────────────────

def test_the_same_provider_event_can_only_pay_once():
    """Polar sends checkout.created AND order.created for one purchase. The
    existing add-on handler credits both, which is the bug this constraint
    exists to make impossible."""
    async def go():
        f = await _fresh_session()
        uid = uuid.uuid4()
        from sqlalchemy.exc import IntegrityError

        async def buy(event_id):
            async with f() as s:
                s.add(CreditPurchase(
                    user_id=uid, provider="polar", provider_event_id=event_id,
                    pack_key="standard", credits=12, amount_minor=1200,
                    currency="USD", status="paid",
                ))
                try:
                    await s.commit()
                except IntegrityError:
                    await s.rollback()
                    return False
                await C.grant_credits(uid, 12, C.KIND_PURCHASE, s)
                return True

        assert await buy("evt_1") is True
        assert await buy("evt_1") is False, "the replay was accepted"
        async with f() as s:
            assert await C.get_balance(uid, s) == 12
    run(go())


def test_two_different_purchases_both_pay():
    async def go():
        f = await _fresh_session()
        uid = uuid.uuid4()
        async with f() as s:
            for ev in ("evt_a", "evt_b"):
                s.add(CreditPurchase(
                    user_id=uid, provider="razorpay", provider_event_id=ev,
                    pack_key="small", credits=4, amount_minor=14900,
                    currency="INR", status="paid",
                ))
                await s.commit()
                await C.grant_credits(uid, 4, C.KIND_PURCHASE, s)
            assert await C.get_balance(uid, s) == 8
    run(go())


# ── 5. The ledger must always explain the balance ────────────────────────────

def test_ledger_and_balance_agree_after_a_busy_life():
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 10)
        gens = [uuid.uuid4() for _ in range(4)]
        async with f() as s:
            for g in gens:
                await C.debit_for_generation(uid, 2, g, s)
        async with f() as s:
            await C.refund_for_generation(gens[0], s)
            await C.refund_for_generation(gens[3], s)
        async with f() as s:
            await C.grant_credits(uid, 5, C.KIND_PATRON_MONTHLY, s)
        async with f() as s:
            drift = await C.reconcile(s)
            assert drift == [], drift
            # 10 - 8 + 4 + 5
            assert await C.get_balance(uid, s) == 11
    run(go())


def test_reconcile_notices_a_tampered_balance():
    """The reconciliation check is only worth having if it would actually
    catch drift, so this proves it does."""
    async def go():
        f = await _fresh_session()
        uid = await _wallet_with(f, 5)
        async with f() as s:
            # Core update, not raw SQL with str(uid): a UUID bound as a string
            # matches nothing where UUIDs are stored dash-less, so the tamper
            # would silently not happen and this test would pass for the wrong
            # reason.
            from sqlalchemy import update as sql_update
            await s.execute(
                sql_update(CreditWallet)
                .where(CreditWallet.user_id == uid)
                .values(balance=99)
            )
            await s.commit()
        async with f() as s:
            drift = await C.reconcile(s)
            assert len(drift) == 1, drift
            assert drift[0]["drift"] == 94, drift
    run(go())


# ── 6. The flag ──────────────────────────────────────────────────────────────

def test_credits_are_off_by_default():
    """Deploying this code must change nothing until the flag is set."""
    os.environ.pop("ASAM_CREDITS_MODE", None)
    assert C.credits_mode() == "off"


def test_the_flag_reads_shadow_and_on():
    for value in ("shadow", "ON", " on "):
        os.environ["ASAM_CREDITS_MODE"] = value
        assert C.credits_mode() == value.strip().lower()
    os.environ.pop("ASAM_CREDITS_MODE", None)


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
                passed += 1
            except AssertionError as e:
                print(f"FAIL  {name}: {e}")
                failed += 1
            except Exception as e:
                print(f"ERROR {name}: {type(e).__name__}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
