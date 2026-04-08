"""
One-time startup migrations.
Each function is idempotent — safe to run on every restart.
Add new migrations as new async functions and call them from run_migrations().
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import Plan, PlanType


# ---------------------------------------------------------------------------
# Target limits for the FREE plan
# ---------------------------------------------------------------------------
FREE_CHAT_LIMIT    = "10"  # 10 conversations (stored as string per existing schema)
FREE_CARD_LIMIT    = 3     # 3 contemplation cards (images)
FREE_MEDITATION    = 5     # 5 minutes = 1 free 5-min audio + 1 free 5-min video


async def _set_free_plan_limits(session: AsyncSession) -> None:
    """
    Ensure the FREE plan's limits match the configured values.
    Only writes to the DB if a value actually needs changing.
    """
    result = await session.execute(
        select(Plan).where(Plan.plan_type == PlanType.FREE)
    )
    free_plans = result.scalars().all()

    if not free_plans:
        print("[MIGRATION] No FREE plan found — skipping limit migration.")
        return

    for plan in free_plans:
        changed = False

        if str(plan.chat_limit) != FREE_CHAT_LIMIT:
            print(f"[MIGRATION] {plan.name}: chat_limit {plan.chat_limit!r} → {FREE_CHAT_LIMIT!r}")
            plan.chat_limit = FREE_CHAT_LIMIT
            changed = True

        if plan.card_limit != FREE_CARD_LIMIT:
            print(f"[MIGRATION] {plan.name}: card_limit {plan.card_limit} → {FREE_CARD_LIMIT}")
            plan.card_limit = FREE_CARD_LIMIT
            changed = True

        if plan.max_meditation_duration != FREE_MEDITATION:
            print(f"[MIGRATION] {plan.name}: max_meditation_duration {plan.max_meditation_duration} → {FREE_MEDITATION}")
            plan.max_meditation_duration = FREE_MEDITATION
            changed = True

        if changed:
            session.add(plan)

    await session.commit()
    print("[MIGRATION] Free plan limits verified/updated.")


async def _add_onboarding_seen_column(session: AsyncSession) -> None:
    """
    Idempotently add onboarding_seen column to user_profiles table.
    Uses IF NOT EXISTS so it is safe to run on every restart.
    """
    await session.execute(text(
        "ALTER TABLE user_profiles "
        "ADD COLUMN IF NOT EXISTS onboarding_seen BOOLEAN NOT NULL DEFAULT FALSE"
    ))
    await session.commit()
    print("[MIGRATION] onboarding_seen column verified/added.")


async def _create_ramana_images_table(session: AsyncSession) -> None:
    """
    Idempotently create the ramana_images table.
    Stores admin-uploaded Ramana / Tiruvannamalai images used for contemplation cards.
    """
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS ramana_images (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            filename    VARCHAR     NOT NULL,
            storage_path VARCHAR    NOT NULL,
            description VARCHAR,
            active      BOOLEAN     NOT NULL DEFAULT TRUE
        )
    """))
    await session.commit()
    print("[MIGRATION] ramana_images table verified/created.")


async def run_migrations(session_factory) -> None:
    """
    Entry point called from server lifespan.
    Runs all migrations in sequence; errors are logged but do NOT crash startup.
    """
    async with session_factory() as session:
        try:
            await _set_free_plan_limits(session)
        except Exception as e:
            print(f"[MIGRATION] ERROR in _set_free_plan_limits: {e}")

        try:
            await _add_onboarding_seen_column(session)
        except Exception as e:
            print(f"[MIGRATION] ERROR in _add_onboarding_seen_column: {e}")

        try:
            await _create_ramana_images_table(session)
        except Exception as e:
            print(f"[MIGRATION] ERROR in _create_ramana_images_table: {e}")
