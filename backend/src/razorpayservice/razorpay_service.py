"""
Razorpay service for Indian INR billing.

INR Pricing (approx 20% discount vs USD at 84 INR/USD):
  Seeker Monthly   Rs.299  / month
  Seeker Yearly    Rs.2699 / year
  Devotee Monthly  Rs.699  / month
  Devotee Yearly   Rs.5399 / year

Design mirrors the Polar integration:
  - RazorpayService class owns all SDK interaction
  - One method per concern: create_subscription, verify_webhook, handle_event
  - Webhook handlers (_on_activated, _on_charged, _on_cancelled) are private
  - No plan creation at checkout time (plans are seeded by migration)
  - All strings passed to the SDK are strictly ASCII
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import (
    BillingCycle,
    Plan,
    PlanType,
    Subscription,
    SubscriptionStatus,
    UserProfile,
)
from src.razorpayservice.razorpay_client import get_razorpay_client
from src.settings import get_settings

logger = logging.getLogger(__name__)

# Tags the subscriptions this service creates. Razorpay delivers every
# subscribed event to EVERY webhook registered on an account, so if a second
# product is ever added to this account its events would arrive here too. The
# tag lets the webhook tell ours apart without relying on the plan lookup alone.
PRODUCT_TAG = "arunachala-samudra"

# ---------------------------------------------------------------------------
# INR plan configuration
# ALL string values MUST be ASCII. The Razorpay SDK sends HTTP requests whose
# Basic-Auth header and JSON body must be latin-1 compatible. Use 'Rs.' not
# the rupee symbol (U+20B9). Use '-' not an em-dash (U+2014).
# ---------------------------------------------------------------------------
INR_PLAN_CONFIG: dict[tuple[PlanType, BillingCycle], dict] = {
    (PlanType.BASIC, BillingCycle.MONTHLY): {
        "name": "Seeker Monthly",
        "description": "Daily practice - audio and video meditation",
        "period": "monthly",
        "interval": 1,
        "amount": 29900,      # Rs.299 in paise
        "currency": "INR",
        "total_count": 60,    # max 5 years of monthly billing
    },
    (PlanType.BASIC, BillingCycle.YEARLY): {
        "name": "Seeker Yearly",
        "description": "Daily practice - audio and video, save 33 percent",
        "period": "yearly",
        "interval": 1,
        "amount": 269900,     # Rs.2699 in paise
        "currency": "INR",
        "total_count": 10,    # max 10 years of yearly billing
    },
    (PlanType.PRO, BillingCycle.MONTHLY): {
        "name": "Devotee Monthly",
        "description": "Unlimited practice - full audio and video access",
        "period": "monthly",
        "interval": 1,
        "amount": 69900,      # Rs.699 in paise
        "currency": "INR",
        "total_count": 60,
    },
    (PlanType.PRO, BillingCycle.YEARLY): {
        "name": "Devotee Yearly",
        "description": "Unlimited practice - save 33 percent",
        "period": "yearly",
        "interval": 1,
        "amount": 539900,     # Rs.5399 in paise
        "currency": "INR",
        "total_count": 10,
    },
}


def _verify_plan_config_is_ascii() -> None:
    """Raise ValueError at import time if any plan config string is not ASCII."""
    for key, cfg in INR_PLAN_CONFIG.items():
        for field in ("name", "description", "period", "currency"):
            value = cfg[field]
            try:
                value.encode("ascii")
            except UnicodeEncodeError as exc:
                raise ValueError(
                    f"INR_PLAN_CONFIG[{key}]['{field}'] contains a non-ASCII character "
                    f"at position {exc.start}: {value!r}"
                ) from exc


# Run at import so misconfiguration is caught immediately at startup.
_verify_plan_config_is_ascii()


# ---------------------------------------------------------------------------
# Public helper — called ONLY from the startup migration, never from a request
# ---------------------------------------------------------------------------

def create_razorpay_plan(plan_type: PlanType, billing_cycle: BillingCycle) -> str:
    """
    Create a Razorpay Plan via the API and return its plan_id (e.g. 'plan_xxx').
    Synchronous — the Razorpay SDK is synchronous.
    Called from migration; wrap in asyncio.to_thread when awaiting.
    """
    key = (plan_type, billing_cycle)
    if key not in INR_PLAN_CONFIG:
        raise ValueError(
            f"No INR plan config for {plan_type.value}/{billing_cycle.value}"
        )

    cfg = INR_PLAN_CONFIG[key]
    client = get_razorpay_client()  # raises ValueError if credentials are bad

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
    plan_id = result.get("id")
    if not plan_id:
        raise RuntimeError(
            f"Razorpay plan.create() returned no id. Full response: {result}"
        )

    logger.info("[RAZORPAY] Created plan '%s' -> %s", cfg["name"], plan_id)
    return plan_id


# ---------------------------------------------------------------------------
# RazorpayService — mirrors PolarService pattern
# ---------------------------------------------------------------------------

class RazorpayService:
    """
    Handles all Razorpay interactions for Indian subscriptions.
    Instantiate per-request (stateless — no shared SDK client state).
    """

    # -- Checkout -----------------------------------------------------------

    def create_subscription(
        self,
        razorpay_plan_id: str,
        user_id: str,
        user_email: str,
        total_count: int,
        callback_url: str | None = None,
    ) -> dict:
        """
        Create a Razorpay Subscription and return:
            {"subscription_id": "sub_xxx", "short_url": "https://rzp.io/..."}

        short_url is the hosted Razorpay checkout page — redirect the user there.
        callback_url: where Razorpay redirects the user after a successful payment.
        Synchronous — wrap in run_in_threadpool when calling from an async endpoint.
        """
        client = get_razorpay_client()

        data: dict = {
            "plan_id": razorpay_plan_id,
            "total_count": total_count,
            "quantity": 1,
            "customer_notify": 1,
            "notes": {
                "user_id": user_id,
                "user_email": user_email,
                # Lets the webhook confirm an event originated here.
                "product": PRODUCT_TAG,
            },
        }
        # Note: callback_url is not supported by Razorpay subscription API in live mode.
        # The redirect after payment is handled via the short_url hosted page.

        result = client.subscription.create(data=data)
        sub_id    = result.get("id")
        short_url = result.get("short_url")

        if not sub_id or not short_url:
            raise RuntimeError(
                f"Razorpay subscription.create() returned unexpected response: {result}"
            )

        logger.info("[RAZORPAY] Created subscription %s for user %s", sub_id, user_id)
        return {"subscription_id": sub_id, "short_url": short_url}

    # -- Synchronous payment verification -----------------------------------

    def verify_payment_signature(
        self,
        razorpay_payment_id: str,
        razorpay_subscription_id: str,
        razorpay_signature: str,
    ) -> bool:
        """
        Verify the signature returned by Razorpay Checkout JS to the success
        handler. Formula:
            expected = HMAC_SHA256(payment_id + "|" + subscription_id, key_secret)
        Returns True if the signature is valid.
        """
        settings = get_settings()
        secret = settings.razorpay_key_secret or ""
        if not secret:
            logger.error("[RAZORPAY] key_secret not configured — cannot verify signature")
            return False

        message = f"{razorpay_payment_id}|{razorpay_subscription_id}".encode("utf-8")
        expected = hmac.new(
            secret.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, razorpay_signature)

    def fetch_subscription(self, subscription_id: str) -> dict:
        """
        Fetch a subscription from Razorpay. Synchronous — wrap in
        run_in_threadpool when calling from an async endpoint.
        """
        client = get_razorpay_client()
        return client.subscription.fetch(subscription_id)

    async def activate_subscription_from_payment(
        self,
        session: AsyncSession,
        user_id: str,
        razorpay_subscription_id: str,
        subscription_data: dict,
    ) -> str:
        """
        Create or update a Subscription row from a verified Razorpay subscription
        payload, and set the user's plan_type. Returns a short status string.

        Mirrors _on_activated but operates on a subscription payload fetched
        from the API (instead of a webhook envelope), so the user sees their
        new plan immediately without waiting for the webhook.
        """
        razorpay_plan_id = subscription_data.get("plan_id")
        status = (subscription_data.get("status") or "").lower()

        if not razorpay_plan_id:
            logger.error("[RAZORPAY] verify: subscription has no plan_id")
            return "missing_plan_id"

        # For a newly completed first payment, status may be 'authenticated' or
        # 'active'. We activate on either. We also treat any subscription with
        # a positive paid_count as activatable — this covers the rare case
        # where the status hasn't flipped yet but money has already been
        # captured (Razorpay occasionally lags on the status transition).
        paid_count = int(subscription_data.get("paid_count") or 0)
        if status not in ("active", "authenticated") and paid_count <= 0:
            logger.warning(
                "[RAZORPAY] verify: subscription %s is in state '%s' with "
                "paid_count=%d — cannot activate (no payment received yet)",
                razorpay_subscription_id, status, paid_count,
            )
            return f"unexpected_status:{status}"

        if status not in ("active", "authenticated") and paid_count > 0:
            logger.info(
                "[RAZORPAY] verify: subscription %s is in state '%s' but has "
                "paid_count=%d — activating on the strength of the recorded "
                "payment despite the lagging status field",
                razorpay_subscription_id, status, paid_count,
            )

        plan_row = (await session.execute(
            select(Plan).where(Plan.razorpay_plan_id == razorpay_plan_id)
        )).scalar_one_or_none()
        if not plan_row:
            logger.error(
                "[RAZORPAY] verify: no Plan found for razorpay_plan_id=%s",
                razorpay_plan_id,
            )
            return "plan_not_found"

        user = (await session.execute(
            select(UserProfile).where(UserProfile.id == user_id)
        )).scalar_one_or_none()
        if not user:
            logger.error("[RAZORPAY] verify: no UserProfile for user_id=%s", user_id)
            return "user_not_found"

        db_sub_id = f"rzp_{razorpay_subscription_id}"

        start_ts = subscription_data.get("current_start")
        end_ts   = subscription_data.get("current_end")
        period_start = (
            datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts
            else datetime.now(timezone.utc)
        )
        period_end = (
            datetime.fromtimestamp(end_ts, tz=timezone.utc) if end_ts
            else None
        )

        existing = (await session.execute(
            select(Subscription).where(Subscription.polar_subscription_id == db_sub_id)
        )).scalar_one_or_none()

        if existing:
            existing.status               = SubscriptionStatus.ACTIVE
            existing.plan_id              = plan_row.id
            existing.current_period_start = period_start
            existing.current_period_end   = period_end
            existing.cancel_at_period_end = False
            session.add(existing)
        else:
            session.add(Subscription(
                id=uuid4(),
                user_id=user_id,
                plan_id=plan_row.id,
                polar_subscription_id=db_sub_id,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=period_start,
                current_period_end=period_end,
                cancel_at_period_end=False,
            ))

        user.plan_type = plan_row.plan_type
        session.add(user)
        await session.commit()

        logger.info(
            "[RAZORPAY] Sync-activated subscription %s -> plan '%s' for user %s",
            razorpay_subscription_id, plan_row.name, user_id,
        )
        return "activated"

    # -- Webhook ------------------------------------------------------------

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """
        Verify the X-Razorpay-Signature header using HMAC-SHA256.

        Fails CLOSED when no secret is configured.

        This handler activates paid subscriptions from a user_id read straight
        out of the payload, so accepting an unverified request would let anyone
        who can reach the endpoint grant themselves a paid plan. The secret is
        configured, so there is no reason to ever accept an unsigned request
        again. The `prod` flag defaults to False and cannot be used to gate this.
        """
        settings = get_settings()
        secret = settings.razorpay_webhook_secret
        if not secret:
            logger.error(
                "[RAZORPAY] Rejecting webhook: ASAM_RAZORPAY_WEBHOOK_SECRET is "
                "not set, so the signature cannot be verified."
            )
            return False

        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def handle_event(
        self,
        session: AsyncSession,
        event: str,
        payload: dict,
    ) -> str:
        """Dispatch a verified webhook event. Returns a short status string."""
        handlers = {
            "subscription.activated": self._on_activated,
            "subscription.charged":   self._on_charged,
            "subscription.cancelled": self._on_cancelled,
            "subscription.completed": self._on_cancelled,
        }
        handler = handlers.get(event)
        if handler is None:
            logger.info("[RAZORPAY] Ignoring unhandled event: %s", event)
            return "unhandled"
        return await handler(session, payload)

    # -- Private event handlers ---------------------------------------------

    async def _on_activated(self, session: AsyncSession, payload: dict) -> str:
        """subscription.activated — create or update the Subscription row."""
        sub_entity       = payload.get("subscription", {}).get("entity", {})
        razorpay_sub_id  = sub_entity.get("id")
        razorpay_plan_id = sub_entity.get("plan_id")
        notes            = sub_entity.get("notes", {})
        user_id          = notes.get("user_id")

        # Ignore anything explicitly tagged as another product. Subscriptions
        # created before the tag existed do not carry it, so those fall through
        # to the plan lookup below, which only matches ids in our Plan table.
        product = notes.get("product")
        if product and product != PRODUCT_TAG:
            logger.info(
                "[RAZORPAY] Ignoring subscription.activated for product=%r "
                "(this service handles %r only)", product, PRODUCT_TAG,
            )
            return "not_our_product"

        if not razorpay_sub_id or not user_id:
            logger.error("[RAZORPAY] activated: missing sub_id or user_id in payload")
            return "missing_fields"

        plan_row = (await session.execute(
            select(Plan).where(Plan.razorpay_plan_id == razorpay_plan_id)
        )).scalar_one_or_none()
        if not plan_row:
            # Not one of our plans. Logged at info rather than error: this is
            # an event we simply do not own, not a failure on our side.
            logger.info(
                "[RAZORPAY] Ignoring event for unknown razorpay_plan_id=%s "
                "(not one of our plans)",
                razorpay_plan_id,
            )
            return "plan_not_found"

        user = (await session.execute(
            select(UserProfile).where(UserProfile.id == user_id)
        )).scalar_one_or_none()
        if not user:
            logger.error(
                "[RAZORPAY] activated: no UserProfile found for user_id=%s", user_id
            )
            return "user_not_found"

        # Store with 'rzp_' prefix to distinguish from Polar subscription IDs
        # in the shared polar_subscription_id column (UNIQUE NOT NULL constraint).
        db_sub_id = f"rzp_{razorpay_sub_id}"

        start_ts = sub_entity.get("current_start")
        end_ts   = sub_entity.get("current_end")
        period_start = (
            datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts
            else datetime.now(timezone.utc)
        )
        period_end = (
            datetime.fromtimestamp(end_ts, tz=timezone.utc) if end_ts
            else None
        )

        existing = (await session.execute(
            select(Subscription).where(Subscription.polar_subscription_id == db_sub_id)
        )).scalar_one_or_none()

        if existing:
            existing.status               = SubscriptionStatus.ACTIVE
            existing.plan_id              = plan_row.id
            existing.current_period_start = period_start
            existing.current_period_end   = period_end
            existing.cancel_at_period_end = False
            session.add(existing)
        else:
            session.add(Subscription(
                id=uuid4(),
                user_id=user_id,
                plan_id=plan_row.id,
                polar_subscription_id=db_sub_id,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=period_start,
                current_period_end=period_end,
                cancel_at_period_end=False,
            ))

        user.plan_type = plan_row.plan_type
        session.add(user)
        await session.commit()

        logger.info(
            "[RAZORPAY] Subscription activated: %s -> plan '%s' for user %s",
            razorpay_sub_id, plan_row.name, user_id,
        )
        return "activated"

    async def _on_charged(self, session: AsyncSession, payload: dict) -> str:
        """subscription.charged — renewal payment received. Subscription stays active."""
        sub_entity = payload.get("subscription", {}).get("entity", {})
        sub_id = sub_entity.get("id", "unknown")
        logger.info("[RAZORPAY] Renewal payment received for subscription %s", sub_id)
        return "charged_ok"

    async def _on_cancelled(self, session: AsyncSession, payload: dict) -> str:
        """subscription.cancelled / subscription.completed — cancel and revert to FREE."""
        sub_entity      = payload.get("subscription", {}).get("entity", {})
        razorpay_sub_id = sub_entity.get("id")
        if not razorpay_sub_id:
            return "missing_sub_id"

        db_sub_id = f"rzp_{razorpay_sub_id}"
        sub = (await session.execute(
            select(Subscription).where(Subscription.polar_subscription_id == db_sub_id)
        )).scalar_one_or_none()

        if not sub:
            logger.warning(
                "[RAZORPAY] Cancel event for unknown subscription %s", razorpay_sub_id
            )
            return "not_found"

        sub.status               = SubscriptionStatus.CANCELED
        sub.cancel_at_period_end = True
        sub.canceled_at          = datetime.now(timezone.utc)
        session.add(sub)

        user = (await session.execute(
            select(UserProfile).where(UserProfile.id == sub.user_id)
        )).scalar_one_or_none()
        if user:
            user.plan_type = PlanType.FREE
            session.add(user)

        await session.commit()
        logger.info("[RAZORPAY] Subscription cancelled: %s", razorpay_sub_id)
        return "cancelled"
