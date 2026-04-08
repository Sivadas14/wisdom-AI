"""
One-time startup migrations.
Each function is idempotent — safe to run on every restart.
Add new migrations as new async functions and call them from run_migrations().
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import Plan, PlanType, BillingCycle


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
        print("[MIGRATION] No FREE plan found — skipping.")
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
                print(f"[MIGRATION] FREE {attr}: {current!r} → {target!r}")
                setattr(plan, attr, target)
                changed = True

        if changed:
            session.add(plan)

    await session.commit()
    print("[MIGRATION] Free (Explore) plan verified/updated.")


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
                print(f"[MIGRATION] {plan.plan_type}/{plan.billing_cycle} {attr}: {getattr(plan, attr)!r} → {target!r}")
                setattr(plan, attr, target)
                changed = True

        if changed:
            session.add(plan)

    await session.commit()
    print("[MIGRATION] Paid plan limits (Seeker/Devotee) verified/updated.")


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
            print(f"[MIGRATION] Skipping Polar update for {plan.name} — no real polar_plan_id")
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
            print(f"[MIGRATION] Polar updated: {new_name} → ${price_cents/100:.2f}")
        except Exception as e:
            print(f"[MIGRATION] Polar update FAILED for {plan.name}: {e}")


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
    print("[MIGRATION] razorpay_plan_id column verified/added to plans.")


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
        print("[MIGRATION] Razorpay not configured — skipping plan creation.")
        return

    result = await session.execute(select(Plan))
    all_plans = result.scalars().all()

    for plan in all_plans:
        if plan.plan_type == PlanType.FREE:
            continue
        if plan.razorpay_plan_id:
            print(f"[MIGRATION] Razorpay plan already exists for {plan.name}: {plan.razorpay_plan_id}")
            continue

        try:
            rzp_plan_id = await asyncio.to_thread(
                create_razorpay_plan, plan.plan_type, plan.billing_cycle
            )
            plan.razorpay_plan_id = rzp_plan_id
            session.add(plan)
            print(f"[MIGRATION] Razorpay plan created for {plan.name} → {rzp_plan_id}")
        except Exception as e:
            print(f"[MIGRATION] Razorpay plan creation FAILED for {plan.name}: {e}")

    await session.commit()
    print("[MIGRATION] Razorpay plans verified/created.")


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
            await _update_paid_plan_limits(session)
        except Exception as e:
            print(f"[MIGRATION] ERROR in _update_paid_plan_limits: {e}")

        try:
            await _update_polar_plan_prices(session)
        except Exception as e:
            print(f"[MIGRATION] ERROR in _update_polar_plan_prices: {e}")

        try:
            await _add_onboarding_seen_column(session)
        except Exception as e:
            print(f"[MIGRATION] ERROR in _add_onboarding_seen_column: {e}")

        try:
            await _create_ramana_images_table(session)
        except Exception as e:
            print(f"[MIGRATION] ERROR in _create_ramana_images_table: {e}")

        try:
            await _add_razorpay_columns(session)
        except Exception as e:
            print(f"[MIGRATION] ERROR in _add_razorpay_columns: {e}")

        try:
            await _create_razorpay_plans(session)
        except Exception as e:
            print(f"[MIGRATION] ERROR in _create_razorpay_plans: {e}")
