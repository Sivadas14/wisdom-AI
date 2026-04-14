"""
One-time startup migrations.
Each function is idempotent — safe to run on every restart.
Add new migrations as new async functions and call them from run_migrations().
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from tuneapi import tu

from src.db import Plan, PlanType, BillingCycle


def _log(msg: str) -> None:
    """Log via tu.logger so output is guaranteed to appear in Render logs.
    Plain print() can be lost to stdout buffering even with PYTHONUNBUFFERED."""
    tu.logger.info(f"[MIGRATION] {msg}")


# ---------------------------------------------------------------------------
# Target limits — all plans
# ---------------------------------------------------------------------------

# FREE / Explore
FREE_PLAN_NAME     = "Explore"
FREE_CHAT_LIMIT    = "20"   # 20 conversations lifetime
FREE_CARD_LIMIT    = 5      # 5 contemplation cards
FREE_MEDITATION    = 5      # 5 minutes lifetime (1 audio + 1 video trial)
FREE_IS_AUDIO      = True
FREE_IS_VIDEO      = True   # video enabled on free (trial)

# BASIC → Seeker
SEEKER_MONTHLY_NAME = "Seeker"
SEEKER_YEARLY_NAME  = "Seeker (Yearly)"
SEEKER_CHAT_MONTHLY = "150"   # 150 conversations/month
SEEKER_CHAT_YEARLY  = "1800"  # 150 × 12
SEEKER_CARD_LIMIT   = 9999    # effectively unlimited
SEEKER_MED_MONTHLY  = 60      # 60 min/month audio+video
SEEKER_MED_YEARLY   = 720     # 60 × 12
SEEKER_IS_AUDIO     = True
SEEKER_IS_VIDEO     = True

# PRO → Devotee
DEVOTEE_MONTHLY_NAME = "Devotee"
DEVOTEE_YEARLY_NAME  = "Devotee (Yearly)"
DEVOTEE_CHAT_LIMIT   = "Unlimited"
DEVOTEE_CARD_LIMIT   = 9999   # effectively unlimited
DEVOTEE_MED_MONTHLY  = 200    # 200 min/month
DEVOTEE_MED_YEARLY   = 2400   # 200 × 12
DEVOTEE_IS_AUDIO     = True
DEVOTEE_IS_VIDEO     = True


async def _set_free_plan_limits(session: AsyncSession) -> None:
    """Ensure FREE plan limits, name, and feature flags are up-to-date."""
    result = await session.execute(
        select(Plan).where(Plan.plan_type == PlanType.FREE)
    )
    free_plans = result.scalars().all()

    if not free_plans:
        _log("No FREE plan found — skipping.")
        return

    for plan in free_plans:
        changed = False

        for attr, target in [
            ("name",                   FREE_PLAN_NAME),
            ("chat_limit",             FREE_CHAT_LIMIT),
            ("card_limit",             FREE_CARD_LIMIT),
            ("max_meditation_duration",FREE_MEDITATION),
            ("is_audio",               FREE_IS_AUDIO),
            ("is_video",               FREE_IS_VIDEO),
        ]:
            current = getattr(plan, attr)
            # Compare as strings for chat_limit (stored as string in DB)
            if str(current) != str(target):
                _log(f"FREE {attr}: {current!r} → {target!r}")
                setattr(plan, attr, target)
                changed = True

        if changed:
            session.add(plan)

    await session.commit()
    _log("Free (Explore) plan verified/updated.")


async def _update_paid_plan_limits(session: AsyncSession) -> None:
    """
    Rename Basic→Seeker and Pro→Devotee; update limits and enable video on Seeker.
    Idempotent — only writes when values differ.
    """
    result = await session.execute(select(Plan))
    all_plans = result.scalars().all()

    for plan in all_plans:
        changed = False
        targets: dict = {}

        if plan.plan_type == PlanType.BASIC:
            if plan.billing_cycle == BillingCycle.MONTHLY:
                targets = {
                    "name": SEEKER_MONTHLY_NAME,
                    "chat_limit": SEEKER_CHAT_MONTHLY,
                    "card_limit": SEEKER_CARD_LIMIT,
                    "max_meditation_duration": SEEKER_MED_MONTHLY,
                    "is_audio": SEEKER_IS_AUDIO,
                    "is_video": SEEKER_IS_VIDEO,
                }
            else:  # YEARLY
                targets = {
                    "name": SEEKER_YEARLY_NAME,
                    "chat_limit": SEEKER_CHAT_YEARLY,
                    "card_limit": SEEKER_CARD_LIMIT,
                    "max_meditation_duration": SEEKER_MED_YEARLY,
                    "is_audio": SEEKER_IS_AUDIO,
                    "is_video": SEEKER_IS_VIDEO,
                }

        elif plan.plan_type == PlanType.PRO:
            if plan.billing_cycle == BillingCycle.MONTHLY:
                targets = {
                    "name": DEVOTEE_MONTHLY_NAME,
                    "chat_limit": DEVOTEE_CHAT_LIMIT,
                    "card_limit": DEVOTEE_CARD_LIMIT,
                    "max_meditation_duration": DEVOTEE_MED_MONTHLY,
                    "is_audio": DEVOTEE_IS_AUDIO,
                    "is_video": DEVOTEE_IS_VIDEO,
                }
            else:  # YEARLY
                targets = {
                    "name": DEVOTEE_YEARLY_NAME,
                    "chat_limit": DEVOTEE_CHAT_LIMIT,
                    "card_limit": DEVOTEE_CARD_LIMIT,
                    "max_meditation_duration": DEVOTEE_MED_YEARLY,
                    "is_audio": DEVOTEE_IS_AUDIO,
                    "is_video": DEVOTEE_IS_VIDEO,
                }

        for attr, target in targets.items():
            if str(getattr(plan, attr)) != str(target):
                _log(f"{plan.plan_type}/{plan.billing_cycle} {attr}: {getattr(plan, attr)!r} → {target!r}")
                setattr(plan, attr, target)
                changed = True

        if changed:
            session.add(plan)

    await session.commit()
    _log("Paid plan limits (Seeker/Devotee) verified/updated.")


async def _update_polar_plan_prices(session: AsyncSession) -> None:
    """
    Sync new pricing to Polar for paid plans:
      Seeker Monthly  $4.99/mo  (unchanged — no-op if already correct)
      Seeker Yearly   $39.99/yr (was $49.99)
      Devotee Monthly $9.99/mo  (was $12.99)
      Devotee Yearly  $79.99/yr (was $129.99)
    Idempotent — skips plans without a valid polar_plan_id.
    """
    import asyncio
    from src.polarservice.polar_plans import update_polar_product
    from src.polarservice.polar_utils import Interval

    # (plan_type, billing_cycle) → (price_cents, interval, plan_name, description)
    POLAR_TARGETS = {
        (PlanType.BASIC, BillingCycle.MONTHLY): (499,   Interval.MONTLY, "Seeker",         "Daily practice — audio & video meditation"),
        (PlanType.BASIC, BillingCycle.YEARLY):  (3999,  Interval.YEARLY, "Seeker (Yearly)", "Daily practice — audio & video, save 33%"),
        (PlanType.PRO,   BillingCycle.MONTHLY): (999,   Interval.MONTLY, "Devotee",         "Unlimited practice — full audio & video access"),
        (PlanType.PRO,   BillingCycle.YEARLY):  (7999,  Interval.YEARLY, "Devotee (Yearly)","Unlimited practice, save 33%"),
    }

    result = await session.execute(select(Plan))
    all_plans = result.scalars().all()

    for plan in all_plans:
        key = (plan.plan_type, plan.billing_cycle)
        if key not in POLAR_TARGETS:
            continue
        if not plan.polar_plan_id or plan.polar_plan_id.startswith("prod_"):
            _log(f"Skipping Polar update for {plan.name} — no real polar_plan_id")
            continue

        price_cents, interval, new_name, description = POLAR_TARGETS[key]
        prices = [{"currency": "USD", "amount": price_cents, "interval": interval}]

        try:
            await asyncio.to_thread(
                update_polar_product,
                polar_product_id=plan.polar_plan_id,
                plan_name=new_name,
                description=description,
                billing_cycle=plan.billing_cycle,
                prices=prices,
            )
            _log(f"Polar updated: {new_name} → ${price_cents/100:.2f}")
        except Exception as e:
            _log(f"Polar update FAILED for {plan.name}: {e}")


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
    _log("onboarding_seen column verified/added.")


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
    _log("ramana_images table verified/created.")


async def _add_razorpay_columns(session: AsyncSession) -> None:
    """
    Idempotently add razorpay_plan_id column to plans table.
    This column stores the Razorpay Plan ID (plan_xxx) for INR billing.
    """
    await session.execute(text(
        "ALTER TABLE plans "
        "ADD COLUMN IF NOT EXISTS razorpay_plan_id VARCHAR UNIQUE"
    ))
    await session.commit()
    _log("razorpay_plan_id column verified/added to plans.")


async def _add_content_generation_status(session: AsyncSession) -> None:
    """
    Idempotently add `status` and `error_message` columns to
    content_generations, and backfill existing rows.

    Why: without a status column, a failed background job leaves
    content_path NULL forever and the frontend polls indefinitely.
    After this migration, failed rows are clearly marked and the UI
    can show a real error instead of spinning.

    Safe to run on every restart.
    """
    # 1. Create enum type (Postgres has no CREATE TYPE IF NOT EXISTS,
    #    so we wrap in a DO block that checks pg_type first).
    await session.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'content_status_enum'
            ) THEN
                CREATE TYPE content_status_enum
                    AS ENUM ('pending', 'processing', 'complete', 'failed');
            END IF;
        END$$;
    """))

    # 2. Add status column (default 'pending' so existing rows get a value
    #    without a second UPDATE; we refine via backfill below).
    await session.execute(text("""
        ALTER TABLE content_generations
        ADD COLUMN IF NOT EXISTS status content_status_enum
            NOT NULL DEFAULT 'pending'
    """))

    # 3. Add error_message column.
    await session.execute(text("""
        ALTER TABLE content_generations
        ADD COLUMN IF NOT EXISTS error_message TEXT
    """))

    # 4. Backfill — idempotent: running twice produces the same result
    #    because the WHERE clauses scope to rows still at the default.
    #    Rows with a content_path were generated successfully.
    await session.execute(text("""
        UPDATE content_generations
           SET status = 'complete'
         WHERE content_path IS NOT NULL
           AND status = 'pending'
    """))

    #    Rows without a content_path never finished. If any were genuinely
    #    mid-flight at deploy time they are already orphaned by the restart.
    await session.execute(text("""
        UPDATE content_generations
           SET status = 'failed',
               error_message = COALESCE(
                   error_message,
                   'Generation did not complete before server restart'
               )
         WHERE content_path IS NULL
           AND status = 'pending'
    """))

    await session.commit()
    _log("content_generations status/error_message columns verified + backfilled.")


async def _create_razorpay_plans(session: AsyncSession) -> None:
    """
    Idempotently create Razorpay plans for paid tiers if:
      1. Razorpay credentials are configured (ASAM_RAZORPAY_KEY_ID is set).
      2. The plan does not already have a razorpay_plan_id.

    Plans created:
      Seeker Monthly  → ₹299/mo
      Seeker Yearly   → ₹2,699/yr
      Devotee Monthly → ₹699/mo
      Devotee Yearly  → ₹5,399/yr
    """
    import asyncio
    from src.settings import get_settings
    from src.razorpayservice.razorpay_client import is_razorpay_enabled
    from src.razorpayservice.razorpay_service import create_razorpay_plan

    settings = get_settings()
    if not is_razorpay_enabled():
        _log("Razorpay not configured — skipping plan creation.")
        return

    result = await session.execute(select(Plan))
    all_plans = result.scalars().all()

    for plan in all_plans:
        if plan.plan_type == PlanType.FREE:
            continue
        if plan.razorpay_plan_id:
            _log(f"Razorpay plan already exists for {plan.name}: {plan.razorpay_plan_id}")
            continue

        try:
            rzp_plan_id = await asyncio.to_thread(
                create_razorpay_plan, plan.plan_type, plan.billing_cycle
            )
            plan.razorpay_plan_id = rzp_plan_id
            session.add(plan)
            _log(f"Razorpay plan created for {plan.name} → {rzp_plan_id}")
        except Exception as e:
            _log(f"Razorpay plan creation FAILED for {plan.name}: {e}")

    await session.commit()
    _log("Razorpay plans verified/created.")


async def _force_plan_limits_raw_sql(session: AsyncSession) -> None:
    """
    BULLETPROOF: forcibly UPDATE every plan's limits using raw SQL.

    This bypasses the SQLAlchemy ORM entirely so it cannot be broken by:
      - missing columns referenced by the model
      - aborted transactions
      - lazy-loading errors
      - silent ORM no-ops

    After running, prints the actual DB state for every plan so we can
    verify in Render logs that the right values are landing.

    Idempotent: same UPDATE on every startup is a no-op when values match.
    """
    # 1. FREE / Explore: 20 chats lifetime / 5 cards / 5 min meditation
    await session.execute(text("""
        UPDATE plans
           SET name = 'Explore',
               chat_limit = '20',
               card_limit = 5,
               max_meditation_duration = 5,
               is_audio = TRUE,
               is_video = TRUE
         WHERE plan_type = 'FREE'
    """))

    # 2. SEEKER MONTHLY (BASIC monthly): 150 chats / unlimited cards / 60 min
    await session.execute(text("""
        UPDATE plans
           SET name = 'Seeker',
               chat_limit = '150',
               card_limit = 9999,
               max_meditation_duration = 60,
               is_audio = TRUE,
               is_video = TRUE
         WHERE plan_type = 'BASIC' AND billing_cycle = 'MONTHLY'
    """))

    # 3. SEEKER YEARLY: 1800 chats / unlimited cards / 720 min
    await session.execute(text("""
        UPDATE plans
           SET name = 'Seeker (Yearly)',
               chat_limit = '1800',
               card_limit = 9999,
               max_meditation_duration = 720,
               is_audio = TRUE,
               is_video = TRUE
         WHERE plan_type = 'BASIC' AND billing_cycle = 'YEARLY'
    """))

    # 4. DEVOTEE MONTHLY (PRO monthly): Unlimited chats / unlimited cards / 200 min
    await session.execute(text("""
        UPDATE plans
           SET name = 'Devotee',
               chat_limit = 'Unlimited',
               card_limit = 9999,
               max_meditation_duration = 200,
               is_audio = TRUE,
               is_video = TRUE
         WHERE plan_type = 'PRO' AND billing_cycle = 'MONTHLY'
    """))

    # 5. DEVOTEE YEARLY: Unlimited chats / unlimited cards / 2400 min
    await session.execute(text("""
        UPDATE plans
           SET name = 'Devotee (Yearly)',
               chat_limit = 'Unlimited',
               card_limit = 9999,
               max_meditation_duration = 2400,
               is_audio = TRUE,
               is_video = TRUE
         WHERE plan_type = 'PRO' AND billing_cycle = 'YEARLY'
    """))

    await session.commit()

    # 6. Verification: read back EVERY plan with raw SQL and log it
    result = await session.execute(text("""
        SELECT id, plan_type, billing_cycle, name,
               chat_limit, card_limit, max_meditation_duration,
               is_audio, is_video
          FROM plans
         ORDER BY plan_type, billing_cycle
    """))
    rows = result.fetchall()
    _log("=== PLAN LIMITS AFTER FORCEFUL UPDATE ===")
    for r in rows:
        _log(
            f"  id={r.id} {r.plan_type}/{r.billing_cycle} "
            f"name={r.name!r} chats={r.chat_limit!r} cards={r.card_limit} "
            f"med={r.max_meditation_duration} audio={r.is_audio} video={r.is_video}"
        )
    _log("=== END PLAN LIMITS ===")


async def _safe_migration(session: AsyncSession, name: str, func) -> None:
    """
    Run a migration and roll back the session on failure.
    Without rollback, a failed query leaves the PG transaction in an
    aborted state, causing every subsequent migration to fail too.
    """
    try:
        await func(session)
    except Exception as e:
        _log(f"ERROR in {name}: {e}")
        try:
            await session.rollback()
        except Exception as re:
            _log(f"Rollback also failed for {name}: {re}")


async def run_migrations(session_factory) -> None:
    """
    Entry point called from server lifespan.
    Runs all migrations in sequence; errors are logged but do NOT crash startup.

    IMPORTANT: schema-changing migrations (ALTER/CREATE) MUST run before any
    migration that issues ORM SELECTs against those tables, because the
    SQLAlchemy models reference the new columns and the SELECT will fail
    if the column does not yet exist in the DB.
    """
    # Unmissable entry-point marker. If this line does NOT appear in
    # Render logs at startup, run_migrations is not being called at all
    # (wrong branch deployed, or lifespan not wired up).
    _log("############################################################")
    _log("##  run_migrations() ENTRY POINT REACHED                  ##")
    _log("############################################################")
    async with session_factory() as session:
        # ── Schema migrations first (ALTER / CREATE) ────────────────────────
        await _safe_migration(session, "_add_onboarding_seen_column", _add_onboarding_seen_column)
        await _safe_migration(session, "_create_ramana_images_table", _create_ramana_images_table)
        await _safe_migration(session, "_add_razorpay_columns", _add_razorpay_columns)
        await _safe_migration(session, "_add_content_generation_status", _add_content_generation_status)

        # ── Data migrations (depend on schema being up to date) ─────────────
        await _safe_migration(session, "_set_free_plan_limits", _set_free_plan_limits)
        await _safe_migration(session, "_update_paid_plan_limits", _update_paid_plan_limits)
        await _safe_migration(session, "_update_polar_plan_prices", _update_polar_plan_prices)
        await _safe_migration(session, "_create_razorpay_plans", _create_razorpay_plans)

        # ── BULLETPROOF FINAL PASS: raw SQL forces correct limits regardless
        # of any prior failure. Always runs LAST so it has the last word.
        await _safe_migration(session, "_force_plan_limits_raw_sql", _force_plan_limits_raw_sql)
