"""
Razorpay service — checkout creation and webhook handling.

INR Pricing (20% discount on USD prices at ~84 INR/USD):
  Seeker Monthly  : ₹299  / month
  Seeker Yearly   : ₹2,699 / year
  Devotee Monthly : ₹699  / month
  Devotee Yearly  : ₹5,399 / year
"""

import hashlib
import hmac
import logging
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import (
    Plan,
    PlanType,
    BillingCycle,
    Subscription,
    SubscriptionStatus,
    UserProfile,
)
from src.settings import get_settings
from src.razorpayservice.razorpay_client import get_razorpay_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# INR plan config  (period, interval, amount in paise, billing display)
# ---------------------------------------------------------------------------
INR_PLAN_CONFIG = {
    (PlanType.BASIC, BillingCycle.MONTHLY): {
        "name": "Seeker Monthly",
        "description": "Daily practice — audio & video meditation",
        "period": "monthly",
        "interval": 1,
        "amount": 29900,   # ₹299 in paise
        "currency": "INR",
        "total_count": 60,  # 5 years of monthly billing
    },
    (PlanType.BASIC, BillingCycle.YEARLY): {
        "name": "Seeker Yearly",
        "description": "Daily practice — audio & video, save 33%",
        "period": "yearly",
        "interval": 1,
        "amount": 269900,  # ₹2,699 in paise
        "currency": "INR",
        "total_count": 10,  # 10 years of yearly billing
    },
    (PlanType.PRO, BillingCycle.MONTHLY): {
        "name": "Devotee Monthly",
        "description": "Unlimited practice — full audio & video access",
        "period": "monthly",
        "interval": 1,
        "amount": 69900,   # ₹699 in paise
        "currency": "INR",
        "total_count": 60,
    },
    (PlanType.PRO, BillingCycle.YEARLY): {
        "name": "Devotee Yearly",
        "description": "Unlimited practice, save 33%",
        "period": "yearly",
        "interval": 1,
        "amount": 539900,  # ₹5,399 in paise
        "currency": "INR",
        "total_count": 10,
    },
}


# ---------------------------------------------------------------------------
# Plan management
# ---------------------------------------------------------------------------

def create_razorpay_plan(plan_type: PlanType, billing_cycle: BillingCycle) -> str:
    """
    Create a Razorpay plan and return its plan_id.
    This is a synchronous call (Razorpay SDK is sync).
    """
    key = (plan_type, billing_cycle)
    if key not in INR_PLAN_CONFIG:
        raise ValueError(f"No INR config for {plan_type}/{billing_cycle}")

    cfg = INR_PLAN_CONFIG[key]
    client = get_razorpay_client()

    plan_data = {
        "period": cfg["period"],
        "interval": cfg["interval"],
        "item": {
            "name": cfg["name"],
            "description": cfg["description"],
            "amount": cfg["amount"],
            "currency": cfg["currency"],
        },
        "notes": {
            "plan_type": plan_type.value,
            "billing_cycle": billing_cycle.value,
        },
    }

    result = client.plan.create(data=plan_data)
    razorpay_plan_id = result.get("id")
    if not razorpay_plan_id:
        raise RuntimeError(f"Razorpay plan creation failed: {result}")

    logger.info(f"[RAZORPAY] Created plan {cfg['name']} → {razorpay_plan_id}")
    return razorpay_plan_id


# ---------------------------------------------------------------------------
# Subscription / checkout
# ---------------------------------------------------------------------------

def create_razorpay_subscription(
    razorpay_plan_id: str,
    user_id: str,
    user_email: str,
    plan_type: PlanType,
    billing_cycle: BillingCycle,
    success_url: str,
) -> dict:
    """
    Create a Razorpay subscription for the user and return
    {"subscription_id": ..., "short_url": ...}.
    The short_url is the hosted Razorpay checkout page.
    """
    cfg = INR_PLAN_CONFIG[(plan_type, billing_cycle)]
    client = get_razorpay_client()

    sub_data = {
        "plan_id": razorpay_plan_id,
        "total_count": cfg["total_count"],
        "quantity": 1,
        "customer_notify": 1,
        "notes": {
            "user_id": user_id,
            "user_email": user_email,
        },
    }

    result = client.subscription.create(data=sub_data)
    sub_id = result.get("id")
    short_url = result.get("short_url")

    if not sub_id or not short_url:
        raise RuntimeError(f"Razorpay subscription creation failed: {result}")

    logger.info(f"[RAZORPAY] Created subscription {sub_id} for user {user_id}")
    return {"subscription_id": sub_id, "short_url": short_url}


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------

def verify_razorpay_webhook_signature(payload_body: bytes, signature: str) -> bool:
    """
    Verify Razorpay webhook signature.
    Razorpay uses HMAC-SHA256 of the raw request body with the webhook secret.
    """
    settings = get_settings()
    secret = settings.razorpay_webhook_secret
    if not secret:
        logger.warning("[RAZORPAY] Webhook secret not configured — skipping verification")
        return True  # Allow in dev/test when secret not set

    expected = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Webhook event handler
# ---------------------------------------------------------------------------

async def handle_razorpay_webhook_event(
    session: AsyncSession,
    event: str,
    payload: dict,
) -> str:
    """
    Handle a verified Razorpay webhook event.
    Returns a status string for logging.
    """
    if event == "subscription.activated":
        return await _handle_subscription_activated(session, payload)

    if event == "subscription.charged":
        # Renewal payment — just log for now; subscription is already active
        sub_entity = payload.get("subscription", {}).get("entity", {})
        sub_id = sub_entity.get("id", "unknown")
        logger.info(f"[RAZORPAY] subscription.charged for {sub_id} — renewal OK")
        return "charged_ok"

    if event in ("subscription.cancelled", "subscription.completed"):
        return await _handle_subscription_cancelled(session, payload)

    logger.info(f"[RAZORPAY] Unhandled event: {event}")
    return "unhandled"


async def _handle_subscription_activated(session: AsyncSession, payload: dict) -> str:
    """Activate a Razorpay subscription in our DB."""
    sub_entity = payload.get("subscription", {}).get("entity", {})
    razorpay_sub_id = sub_entity.get("id")
    razorpay_plan_id = sub_entity.get("plan_id")
    notes = sub_entity.get("notes", {})
    user_id = notes.get("user_id")

    current_start_ts = sub_entity.get("current_start")
    current_end_ts = sub_entity.get("current_end")

    if not razorpay_sub_id or not user_id:
        logger.error(f"[RAZORPAY] Missing sub_id or user_id in payload: {payload}")
        return "missing_fields"

    logger.info(f"[RAZORPAY] Activating subscription {razorpay_sub_id} for user {user_id}")

    # Find the plan by razorpay_plan_id
    plan_result = await session.execute(
        select(Plan).where(Plan.razorpay_plan_id == razorpay_plan_id)
    )
    plan = plan_result.scalar_one_or_none()

    if not plan:
        logger.error(f"[RAZORPAY] No plan found for razorpay_plan_id={razorpay_plan_id}")
        return "plan_not_found"

    # Find user
    user_result = await session.execute(
        select(UserProfile).where(UserProfile.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        logger.error(f"[RAZORPAY] No user found for user_id={user_id}")
        return "user_not_found"

    # polar_subscription_id for Razorpay is prefixed with "rzp_" to satisfy NOT NULL UNIQUE
    polar_sub_id_placeholder = f"rzp_{razorpay_sub_id}"

    # Check if subscription already exists (idempotent)
    existing_result = await session.execute(
        select(Subscription).where(
            Subscription.polar_subscription_id == polar_sub_id_placeholder
        )
    )
    existing = existing_result.scalar_one_or_none()

    period_start = (
        datetime.fromtimestamp(current_start_ts, tz=timezone.utc)
        if current_start_ts else datetime.now(timezone.utc)
    )
    period_end = (
        datetime.fromtimestamp(current_end_ts, tz=timezone.utc)
        if current_end_ts else None
    )

    if existing:
        # Update existing
        existing.status = SubscriptionStatus.ACTIVE
        existing.plan_id = plan.id
        existing.current_period_start = period_start
        existing.current_period_end = period_end
        existing.cancel_at_period_end = False
        session.add(existing)
    else:
        # Create new subscription
        new_sub = Subscription(
            id=uuid4(),
            user_id=user_id,
            plan_id=plan.id,
            polar_subscription_id=polar_sub_id_placeholder,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
            cancel_at_period_end=False,
        )
        session.add(new_sub)

    # Update user's plan_type
    user.plan_type = plan.plan_type
    session.add(user)

    await session.commit()
    logger.info(f"[RAZORPAY] ✅ Subscription activated: {razorpay_sub_id} → plan {plan.name}")
    return "activated"


async def _handle_subscription_cancelled(session: AsyncSession, payload: dict) -> str:
    """Mark a Razorpay subscription as cancelled in DB."""
    sub_entity = payload.get("subscription", {}).get("entity", {})
    razorpay_sub_id = sub_entity.get("id")

    if not razorpay_sub_id:
        return "missing_sub_id"

    polar_sub_id_placeholder = f"rzp_{razorpay_sub_id}"

    result = await session.execute(
        select(Subscription).where(
            Subscription.polar_subscription_id == polar_sub_id_placeholder
        )
    )
    sub = result.scalar_one_or_none()

    if not sub:
        logger.warning(f"[RAZORPAY] Subscription {razorpay_sub_id} not found in DB — skipping cancel")
        return "not_found"

    sub.status = SubscriptionStatus.CANCELED
    sub.cancel_at_period_end = True
    sub.canceled_at = datetime.now(timezone.utc)
    session.add(sub)

    # Revert user to FREE plan
    user_result = await session.execute(
        select(UserProfile).where(UserProfile.id == sub.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user:
        user.plan_type = PlanType.FREE
        session.add(user)

    await session.commit()
    logger.info(f"[RAZORPAY] ❌ Subscription cancelled: {razorpay_sub_id}")
    return "cancelled"
