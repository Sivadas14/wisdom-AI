"""Tests for src/services/media_access.py — who pays for media, and how much.

The resolution order is the policy, so it is tested as an order: each rule must
win over the ones below it. A trial that stops working the moment someone's old
plan expires, or a legacy subscriber who gets charged credits, would both be
silent failures that only a paying seeker would notice.
"""
import asyncio
import os
import sys
import types
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.db import Base, CreditTransaction, CreditWallet, PlanType, UserRole  # noqa: E402
from src.services import credits as C  # noqa: E402
from src.services import media_access as M  # noqa: E402


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class FakeUser:
    """Only the four attributes the decision actually reads."""
    def __init__(self, role=UserRole.USER, plan_type=PlanType.FREE, email="a@b.com"):
        self.id = uuid.uuid4()
        self.role = role
        self.plan_type = plan_type
        self.email_id = email


async def _db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[CreditWallet.__table__, CreditTransaction.__table__],
        )
    return async_sessionmaker(engine, expire_on_commit=False)


def _no_trials():
    """No trial grant for anyone. trials.py is stubbed because importing it
    pulls in the FastAPI dependency wiring, which this decision does not use."""
    mod = types.ModuleType("src.services.trials")
    async def active_grant_for(email, session):
        return None
    mod.active_grant_for = active_grant_for
    sys.modules["src.services.trials"] = mod


def _trial_for(email):
    mod = types.ModuleType("src.services.trials")
    async def active_grant_for(e, session):
        return object() if e == email else None
    mod.active_grant_for = active_grant_for
    sys.modules["src.services.trials"] = mod


# ── Length parsing ───────────────────────────────────────────────────────────

def test_lengths_parse():
    assert M.parse_minutes("5 min") == 5
    assert M.parse_minutes("10 min") == 10
    assert M.parse_minutes("20 min") == 20


def test_a_missing_length_falls_back_to_the_shortest():
    """Guessing high would overcharge someone for a malformed request."""
    for bad in (None, "", "   ", "long", "0 min"):
        assert M.parse_minutes(bad) == M.DEFAULT_MINUTES == 5


# ── The resolution order ─────────────────────────────────────────────────────

def test_an_admin_is_never_charged():
    async def go():
        f = await _db(); _no_trials()
        async with f() as s:
            d = await M.decide(FakeUser(role=UserRole.ADMIN), 20, s)
            assert d.allowed and not d.charge, d
            assert d.reason == "admin"
    run(go())


def test_a_trial_beats_an_empty_wallet():
    async def go():
        f = await _db()
        u = FakeUser()
        _trial_for(u.email_id)
        async with f() as s:
            d = await M.decide(u, 20, s)
            assert d.allowed and not d.charge, d
            assert d.reason == "trial"
    run(go())


def test_a_legacy_subscriber_keeps_their_media():
    """They paid for a plan; the plan is being withdrawn from sale, not taken
    away from them."""
    async def go():
        f = await _db(); _no_trials()
        async with f() as s:
            for plan in (PlanType.BASIC, PlanType.PRO):
                d = await M.decide(FakeUser(plan_type=plan), 20, s)
                assert d.allowed and not d.charge, (plan, d)
                assert d.reason == "legacy_plan"
    run(go())


def test_a_free_account_with_credits_pays_credits():
    async def go():
        f = await _db(); _no_trials()
        u = FakeUser()
        async with f() as s:
            await C.grant_credits(u.id, 4, C.KIND_PURCHASE, s)
            d = await M.decide(u, 20, s)
            assert d.allowed and d.charge, d
            assert d.reason == "credits" and d.cost == 4
    run(go())


def test_a_free_account_without_enough_is_refused():
    async def go():
        f = await _db(); _no_trials()
        u = FakeUser()
        async with f() as s:
            await C.grant_credits(u.id, 2, C.KIND_PURCHASE, s)
            d = await M.decide(u, 20, s)       # needs 4
            assert not d.allowed, d
            assert d.reason == "insufficient"
            assert d.cost == 4 and d.balance == 2
    run(go())


def test_an_empty_wallet_is_refused():
    async def go():
        f = await _db(); _no_trials()
        async with f() as s:
            d = await M.decide(FakeUser(), 5, s)
            assert not d.allowed and d.cost == 1 and d.balance == 0
    run(go())


# ── Cost follows length, not medium ──────────────────────────────────────────

def test_cost_rises_with_length():
    async def go():
        f = await _db(); _no_trials()
        u = FakeUser()
        async with f() as s:
            await C.grant_credits(u.id, 99, C.KIND_PURCHASE, s)
            for minutes, expected in [(5, 1), (10, 2), (15, 3), (20, 4)]:
                d = await M.decide(u, minutes, s)
                assert d.cost == expected, (minutes, d)
    run(go())


def test_a_broken_trial_lookup_does_not_open_the_gate():
    """If grants cannot be read, the seeker falls through to the paid checks.
    Failing open here would hand free media to everyone during a database
    hiccup."""
    async def go():
        f = await _db()
        mod = types.ModuleType("src.services.trials")
        async def boom(email, session):
            raise RuntimeError("db down")
        mod.active_grant_for = boom
        sys.modules["src.services.trials"] = mod
        async with f() as s:
            d = await M.decide(FakeUser(), 5, s)
            assert not d.allowed, d
            assert d.reason == "insufficient"
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
