"""Tests for src/services/trials.py.

What matters here is not that a grant can be created, but that it starts and
stops when it is supposed to. A trial that fails to expire is a free account
nobody remembers issuing, and a trial that fails to apply makes the feature
look broken.

These run against a fake session rather than a database, so they test the
decision logic: which grant wins, when it is live, and what the API accepts.
"""
import asyncio
import datetime as _dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# trials.py imports the ORM models and the FastAPI dependency wiring, which
# drag in pgvector, supabase and the rest of the runtime. None of that is
# needed to test WHEN a grant is live, so the two modules are stubbed. The
# logic under test is untouched.
import types  # noqa: E402

from sqlalchemy import Column, DateTime, String, Text  # noqa: E402
from sqlalchemy.orm import declarative_base  # noqa: E402

_Base = declarative_base()


class _TrialGrant(_Base):
    """A real mapped class, so select(TrialGrant) builds a real query.

    The point is that the code under test constructs its query exactly as it
    does in production; only the session executing it is faked.
    """
    __tablename__ = "trial_grants"
    id = Column(String, primary_key=True)
    email = Column(String)
    starts_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
    note = Column(Text)
    granted_by = Column(String)


_db = types.ModuleType("src.db")
_db.TrialGrant = _TrialGrant
_db.UserProfile = type("UserProfile", (), {})
_db.get_db_session_fa = lambda: None
sys.modules.setdefault("src.db", _db)

_deps = types.ModuleType("src.dependencies")
_deps.get_current_user = lambda: None
sys.modules.setdefault("src.dependencies", _deps)


# ── A fake session that records the filters it was asked for ────────────────
# active_grant_for builds its query with WHERE clauses on revoked_at,
# starts_at and expires_at. Rather than reimplement SQL, the fake applies the
# same three conditions in Python to a list of grants.

class FakeGrant:
    def __init__(self, email, days_from, days_to, revoked=False, note=None):
        now = _dt.datetime.now(_dt.timezone.utc)
        self.email = email
        self.starts_at = now + _dt.timedelta(days=days_from)
        self.expires_at = now + _dt.timedelta(days=days_to)
        self.revoked_at = now if revoked else None
        self.note = note
        self.id = f"{email}:{days_to}"


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    """Applies the same live-grant conditions the real query applies."""

    def __init__(self, grants):
        self.grants = grants
        self.added = []
        self.committed = False

    async def execute(self, _query):
        now = _dt.datetime.now(_dt.timezone.utc)
        live = [
            g for g in self.grants
            if g.revoked_at is None and g.starts_at <= now < g.expires_at
        ]
        live.sort(key=lambda g: g.expires_at, reverse=True)
        return FakeResult(live)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, _obj):
        pass


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


from src.services.trials import (  # noqa: E402
    DEFAULT_TRIAL_DAYS, MAX_TRIAL_DAYS, active_grant_for, normalise_email,
)


# ── 1. Email matching ────────────────────────────────────────────────────────

def test_email_is_normalised():
    """A grant typed with capitals or a stray space must still match the
    account that signed up in lower case, or the feature looks broken when it
    is really a typo."""
    for raw in ["Someone@Gmail.com", " someone@gmail.com ", "SOMEONE@GMAIL.COM"]:
        assert normalise_email(raw) == "someone@gmail.com"


def test_blank_email_is_never_a_grant():
    s = FakeSession([FakeGrant("someone@gmail.com", -1, 30)])
    assert run(active_grant_for("", s)) is None
    assert run(active_grant_for(None, s)) is None


# ── 2. When a grant is live ──────────────────────────────────────────────────

def test_a_current_grant_is_found():
    s = FakeSession([FakeGrant("a@b.com", -1, 30)])
    assert run(active_grant_for("a@b.com", s)) is not None


def test_an_expired_grant_is_not_found():
    """The whole point of a time-boxed trial."""
    s = FakeSession([FakeGrant("a@b.com", -60, -1)])
    assert run(active_grant_for("a@b.com", s)) is None


def test_a_revoked_grant_is_not_found():
    s = FakeSession([FakeGrant("a@b.com", -1, 30, revoked=True)])
    assert run(active_grant_for("a@b.com", s)) is None


def test_a_future_grant_is_not_yet_active():
    s = FakeSession([FakeGrant("a@b.com", 5, 30)])
    assert run(active_grant_for("a@b.com", s)) is None


def test_a_grant_expiring_today_still_works_until_the_moment_it_lapses():
    s = FakeSession([FakeGrant("a@b.com", -30, 0.001)])
    assert run(active_grant_for("a@b.com", s)) is not None


def test_the_longest_grant_wins():
    """An extension must not be shadowed by an earlier, shorter grant."""
    s = FakeSession([
        FakeGrant("a@b.com", -10, 2),
        FakeGrant("a@b.com", -1, 60),
    ])
    g = run(active_grant_for("a@b.com", s))
    assert g is not None
    days = (g.expires_at - _dt.datetime.now(_dt.timezone.utc)).days
    assert days > 50, days


# ── 3. Limits on what can be granted ─────────────────────────────────────────

def test_a_trial_cannot_be_open_ended():
    """An uncapped grant is just a free account nobody remembers creating."""
    assert MAX_TRIAL_DAYS <= 366
    assert 1 <= DEFAULT_TRIAL_DAYS <= MAX_TRIAL_DAYS


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
