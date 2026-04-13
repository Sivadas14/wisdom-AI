from fastapi import APIRouter, Depends, Request, HTTPException ,Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from decimal import Decimal
from fastapi.concurrency import run_in_threadpool
from datetime import datetime, timezone
from src.db import Subscription, SubscriptionStatus, Plan
from src.polarservice.polar_client import get_polar_client
import json
from fastapi import Query
from src.db import get_db_session, Plan
from src.dependencies import get_current_user
from src.services.pollor_service import PollorService
from src.services.subscription import (
    calculate_proration,
    create_checkout_session,
    handle_checkout_success,
    handle_subscription_revoked,
    sync_user_subscription,
    handle_checkout_success_with_periods,
    cancel_user_subscription,
    calculate_downgrade_proration,
    downgrade_subscription,
)
from src.settings import get_settings
from src.wire import SuccessResponse
from src.db import (
    get_db_session, 
  Subscription,
  SubscriptionStatus
)
import traceback

from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

from src.db import (
    Subscription, 
    SubscriptionStatus, 
    UserProfile, 
    Plan, 
    PlanType
)
router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])


# ============================================================================
# UPGRADE ENDPOINTS
# ============================================================================

@router.get("/upgrade/previews")
async def preview_upgrade(
    polar_product_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Preview upgrade cost with proration breakdown.
    
    Shows:
    - Current plan details
    - New plan details
    - Prorated amount to be charged today
    - Days remaining in billing cycle
    - Next billing date
    
    This is for display purposes only - actual proration is handled by Polar.
    """
    try:
        preview = await calculate_detailed_proration(
            session=session,
            user_id=user_id,
            polar_product_id=polar_product_id
        )
        
        if "error" in preview:
            raise HTTPException(
                status_code=400,
                detail=preview["error"]
            )
        
        return SuccessResponse(
            message="Upgrade preview calculated",
            data=preview
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Preview error: {str(e)}")
        
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/checkout")
async def create_checkout(
    polar_product_id: str = Query(...),
    user_id: str = Query(...),
    redirect_url: str = Query(...),
    session: AsyncSession = Depends(get_db_session)
):
    try:
        print("-" * 50)
        print("ENTER IN CHECKOUT")
        url = await create_checkout_session(polar_product_id, user_id,redirect_url,session)
        return SuccessResponse(message="Checkout URL generated", data={"checkout_url": url})
    except Exception as e:
        print(f"ERROR IN CHECKOUT: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/webhook")
async def polar_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    print("🔔 Polar webhook received")

    try:
        payload = await request.json()
    except Exception as e:
        print(f"❌ Failed to parse JSON payload: {e}")
        return {"status": "invalid_json"}

    # ---- RAW PAYLOAD DEBUG ----
    print("📦 Raw Payload:")
    print(json.dumps(payload, indent=2, default=str))

    event_type = payload.get("type")
    data = payload.get("data", {})

    print(f"📌 Event Type: {event_type}")

    if not data:
        print("⚠️ Webhook data is empty")
        return {"status": "no_data"}

    # ---- COMMON FIELDS ----
    if event_type == "order.created":
        polar_subscription_id = data.get("subscription_id")
    else:
        polar_subscription_id = data.get("id")
        
    polar_product_id = data.get("product_id")
    polar_price_id = data.get("price_id")
    polar_customer_id = data.get("customer_id")
    status = data.get("status")
    metadata = data.get("metadata", {})
    
    # Extract period information from webhook payload
    current_period_start = data.get("current_period_start")
    current_period_end = data.get("current_period_end")
    cancel_at_period_end = data.get("cancel_at_period_end", False)

    # For order.created, we might not have period info in the order object itself
    # but handle_checkout_success_with_periods can deal with it or we could fetch it.

    print("🧾 Subscription Details:")
    print(f"   Subscription ID : {polar_subscription_id}")
    print(f"   Product ID      : {polar_product_id}")
    print(f"   Price ID        : {polar_price_id}")
    print(f"   Customer ID     : {polar_customer_id}")
    print(f"   Status          : {status}")
    if current_period_start:
        print(f"   Period Start    : {current_period_start}")
    if current_period_end:
        print(f"   Period End      : {current_period_end}")
    print(f"   Cancel at End   : {cancel_at_period_end}")
    print(f"   Metadata        : {metadata}")
  # 1. Check for Addon Purchase (Metadata overrides standard logic usually)
    metadata = data.get("metadata", {})
    if metadata.get("type") == "addon_purchase":
        logger.info("Routing to PollorService (Addon Purchase)")
        return await PollorService.handle_webhook(session, payload)
        
    # ---- ACTIVE / UPDATED SUBSCRIPTION / ORDER ----
    if event_type in ("subscription.created", "subscription.updated", "subscription.active", "order.created"):
        # For order.created, status might be 'paid' or 'succeeded' or None
        # For subscriptions, status is 'active'
        is_order = event_type == "order.created"
        should_process = (status == "active") or (is_order and polar_subscription_id)
        
        if should_process:
            print(f"✅ {'Order' if is_order else 'Subscription'} detected → processing success")

            try:
                await handle_checkout_success_with_periods(
                    session=session,
                    polar_subscription_id=polar_subscription_id,
                    polar_customer_id=polar_customer_id,
                    polar_product_id=polar_product_id,
                    polar_price_id=polar_price_id,
                    current_period_start=current_period_start,
                    current_period_end=current_period_end,
                    cancel_at_period_end=cancel_at_period_end,
                    metadata=metadata
                )
                print("🎉 Subscription successfully synced")

            except Exception as e:
                print("❌ Error while handling active subscription")
                print(f"❌ Error details: {e}")
                return {"status": "handler_error", "error": str(e)}

        else:
            print(f"ℹ️ Subscription status is '{status}', skipping activation")

    # ---- CANCELED / REVOKED ----
    elif event_type in ("subscription.revoked"):
        print("🚫 Subscription revoked or canceled")

        try:
            await handle_subscription_revoked(session, polar_subscription_id)
            print("🗑️ Subscription successfully revoked in DB")
        except Exception as e:
            print("❌ Error revoking subscription")
            print(f"❌ Error details: {e}")
            return {"status": "revoke_error", "error": str(e)}

    else:
        print(f"🤷 Unhandled event type: {event_type}")

    return {"status": "received"}



# ========================================================================
# FRONTEND-READY ENDPOINTS
# ========================================================================

@router.post("/upgrade/checkout")
async def create_upgrade_checkout_endpoint(
    polar_product_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Create checkout URL for upgrading subscription.
    Frontend passes Polar Product ID (from plan.polar_plan_id).
    """
    try:
        result = await direct_subscription_upgrade(
            session=session,
            user_id=user_id,
            polar_product_id=polar_product_id,
            prorate=True
        )
        
        return SuccessResponse(
            message="Upgrade checkout created",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




@router.get("/sync")
async def sync_subscription(
    request: Request,
    user_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Manually triggers subscription sync with Polar. 
    Frontend should call this after checkout success or on subscription load.
    """
    try:
        is_active = await sync_user_subscription(session, user_id)
        status_msg = "User has active subscription" if is_active else "No active subscription found"
        return SuccessResponse(message=status_msg, data={"is_active": is_active})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    


# ---------- Helpers ----------

def ensure_utc(dt):
    """Ensure datetime is timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def extract_price(plan) -> float:
    """Safely extract price from Plan.prices."""
    if not plan or not plan.prices:
        return 0.0

    for price in plan.prices:
        amount = getattr(price, "price", None) or getattr(price, "amount", None)
        if isinstance(amount, (int, float, Decimal)):
            return float(amount)

    return 0.0

async def create_verified_upgrade_checkout(
    session: AsyncSession,
    user_id: str,
    polar_product_id: str
) -> dict:
    """
    Create upgrade checkout and verify it shows prorated amount.
    """
    # 1. Get current subscription
    stmt = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.status == SubscriptionStatus.ACTIVE
    ).options(selectinload(Subscription.plan))
    
    result = await session.execute(stmt)
    current_sub = result.scalar_one_or_none()
    
    if not current_sub or not current_sub.polar_subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription found")
    
    # 2. Get new plan
    plan_stmt = select(Plan).where(Plan.polar_plan_id == polar_product_id)
    plan_result = await session.execute(plan_stmt)
    new_plan = plan_result.scalar_one_or_none()
    
    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # 3. Calculate expected proration (for verification)
    def get_monthly_price(plan):
        if plan.prices:
            for price in plan.prices:
                if hasattr(price, 'price'):
                    amount = getattr(price, 'price')
                    if isinstance(amount, (int, float)):
                        return float(amount)
        return 0.0
    
    current_price = get_monthly_price(current_sub.plan)
    new_price = get_monthly_price(new_plan)
    
    # Calculate days remaining
    days_remaining = 0
    if current_sub.current_period_end:
        now = datetime.utcnow()
        if current_sub.current_period_end > now:
            days_remaining = (current_sub.current_period_end - now).days
    
    # Calculate expected prorated amount
    expected_prorated = 0
    if days_remaining > 0:
        price_diff = new_price - current_price
        expected_prorated = price_diff * (days_remaining / 30)  # 30-day month
    
    # 4. Create checkout with subscription parameter
    def _create_checkout():
        with get_polar_client() as polar:
            checkout_payload = {
                "subscription": current_sub.polar_subscription_id,  # KEY: This enables proration
                "products": [polar_product_id],
                 "prices": {
        polar_product_id: [
            {
                "amount": int(round(expected_prorated, 2) * 100),  # Convert to cents
                "currency": "usd"
            }
        ]
    },
                "success_url": f"{get_settings().frontend_url}/subscription?upgrade=success",
                "cancel_url": f"{get_settings().frontend_url}/subscription?upgrade=cancelled",
                "metadata": {
                    "user_id": user_id,
                    "expected_prorated_amount": str(round(expected_prorated, 2)),
                    "current_price": str(current_price),
                    "new_price": str(new_price)
                }
            }
            
            print(f"DEBUG: Creating upgrade checkout with subscription: {current_sub.polar_subscription_id}")
            session_obj = polar.checkouts.create(request=checkout_payload)
            return session_obj
    
    try:
        checkout_session = await run_in_threadpool(_create_checkout)
        
        return {
            "success": True,
            "checkout_url": checkout_session.url,
            "display_details": {
                "message": "You'll only pay the prorated amount today",
                "expected_today_charge": round(expected_prorated, 2),
                "next_full_charge": new_price,
                "next_billing_date": current_sub.current_period_end.isoformat() if current_sub.current_period_end else None,
                "current_plan": current_sub.plan.name,
                "new_plan": new_plan.name
            },
            "verification": {
                "method": "Polar automatically calculates proration when 'subscription' parameter is provided",
                "checkout_shows": "Only prorated amount, not full price",
                "test_instructions": [
                    "1. Open the checkout URL",
                    "2. Verify it shows 'Today's Charge: $X.XX' (prorated amount)",
                    "3. Verify it does NOT show 'Price: $12.96/month' as a standalone price"
                ]
            }
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"DEBUG: Checkout creation error: {error_msg}")
        
        # If Polar says "already has subscription", it means we're not providing subscription ID correctly
        if "already has an active subscription" in error_msg:
            raise HTTPException(
                status_code=400,
                detail="Prorated checkout failed. The system is trying to create a new subscription instead of upgrading. Please contact support."
            )
        
        raise HTTPException(status_code=400, detail=f"Checkout creation failed: {error_msg}")

@router.post("/upgrade/checkouts")
async def create_upgrade_checkout_endpoint(
    polar_product_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    try:
        result = await create_verified_upgrade_checkouts(
            session=session,
            user_id=user_id,
            polar_product_id=polar_product_id
        )
        return SuccessResponse(
            message="Upgrade checkout created",
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    


# ---------- Main Function ----------

async def create_verified_upgrade_checkouts(
    session: AsyncSession,
    user_id: str,
    polar_product_id: str
) -> dict:
    """
    Create upgrade checkout with comprehensive debug logging.
    """
    logger.info(f"🚀 START create_verified_upgrade_checkouts - user_id: {user_id}, product_id: {polar_product_id}")
    
    # 1️⃣ Load active subscription WITH plan + prices
    logger.debug(f"🔍 1. Querying active subscription for user {user_id}")
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        .options(
            selectinload(Subscription.plan)
            .selectinload(Plan.prices)
        )
    )

    result = await session.execute(stmt)
    current_sub = result.scalar_one_or_none()

    logger.debug(f"📊 Subscription query result: {'Found' if current_sub else 'Not found'}")
    
    if not current_sub:
        logger.error(f"❌ No active subscription found for user {user_id}")
        raise HTTPException(status_code=400, detail="No active subscription found")
    
    if not current_sub.polar_subscription_id:
        logger.error(f"❌ Subscription found but missing polar_subscription_id: {current_sub.id}")
        raise HTTPException(status_code=400, detail="Subscription missing Polar ID")

    logger.info(f"✅ Current subscription: ID={current_sub.id}, Polar_ID={current_sub.polar_subscription_id}")
    logger.debug(f"📝 Current subscription details: plan_id={current_sub.plan_id}, status={current_sub.status}")
    
    # 2️⃣ Load new plan WITH prices
    logger.debug(f"🔍 2. Querying new plan with polar_product_id: {polar_product_id}")
    plan_stmt = (
        select(Plan)
        .where(Plan.polar_plan_id == polar_product_id)
        .options(selectinload(Plan.prices))
    )

    plan_result = await session.execute(plan_stmt)
    new_plan = plan_result.scalar_one_or_none()

    logger.debug(f"📊 Plan query result: {'Found' if new_plan else 'Not found'}")
    
    if not new_plan:
        logger.error(f"❌ Plan not found for polar_product_id: {polar_product_id}")
        raise HTTPException(status_code=404, detail="Plan not found")

    logger.info(f"✅ New plan: ID={new_plan.id}, Name={new_plan.name}, Polar_ID={new_plan.polar_plan_id}")
    
    # 3️⃣ Price extraction with detailed logging
    logger.debug(f"💰 3. Extracting prices from plans")
    
    def get_monthly_price(plan: Plan, plan_name: str) -> float:
        logger.debug(f"  📦 Extracting price from {plan_name}")
        
        if not plan.prices:
            logger.warning(f"  ⚠️ No prices found for {plan_name}")
            return 0.0
        
        logger.debug(f"  🔢 Found {len(plan.prices)} price(s) for {plan_name}")
        
        for i, price in enumerate(plan.prices):
            logger.debug(f"    Price {i}: Type={type(price).__name__}")
            
            # List all attributes for debugging
            attrs = [attr for attr in dir(price) if not attr.startswith('_') and not callable(getattr(price, attr))]
            logger.debug(f"    Price attributes: {attrs[:10]}...")  # Show first 10
            
            # Check for price value
            amount = getattr(price, "price", None)
            logger.debug(f"    Checking 'price' attribute: {amount} (type: {type(amount)})")
            
            if amount is None:
                # Try other common field names
                for field in ['amount', 'monthly_price', 'unit_amount', 'price_amount']:
                    amount = getattr(price, field, None)
                    if amount is not None:
                        logger.debug(f"    Found in field '{field}': {amount}")
                        break
            
            if amount is not None:
                try:
                    price_float = float(amount)
                    logger.info(f"    ✅ Extracted price for {plan_name}: ${price_float:.2f}")
                    return price_float
                except (ValueError, TypeError) as e:
                    logger.warning(f"    ⚠️ Could not convert price {amount} to float: {e}")
                    continue
        
        logger.warning(f"  ⚠️ No valid price found for {plan_name}")
        return 0.0

    current_price = get_monthly_price(current_sub.plan, f"Current Plan ({current_sub.plan.name})")
    new_price = get_monthly_price(new_plan, f"New Plan ({new_plan.name})")
    
    logger.info(f"📊 Price comparison: Current=${current_price:.2f} → New=${new_price:.2f}")
    
    # 4️⃣ Calculate remaining days with timezone awareness
    logger.debug(f"📅 4. Calculating billing cycle details")
    
    now = datetime.now(timezone.utc)
    logger.debug(f"  ⏰ Current UTC time: {now.isoformat()}")
    
    days_remaining = 26
    period_end_iso = 26.0
    
    if current_sub.current_period_end:
        # Handle timezone - ensure we're comparing UTC times
        if current_sub.current_period_end.tzinfo is None:
            # Assume UTC if no timezone info
            period_end = current_sub.current_period_end.replace(tzinfo=timezone.utc)
            logger.debug(f"  ⚠️ current_period_end had no timezone, assumed UTC: {period_end}")
        else:
            period_end = current_sub.current_period_end.astimezone(timezone.utc)
        
        period_end_iso = period_end.isoformat()
        logger.debug(f"  📅 Billing period ends at: {period_end_iso}")
        
        if period_end > now:
            days_remaining = (period_end - now).days
            seconds_remaining = (period_end - now).total_seconds()
            exact_days = seconds_remaining / (24 * 3600)
            
            logger.info(f"  📆 Days remaining: {days_remaining} days (exact: {exact_days:.2f} days)")
            logger.debug(f"  ⏱️ Seconds remaining: {seconds_remaining:.0f}")
        else:
            logger.warning(f"  ⚠️ Billing period has already ended or ends today")
            logger.debug(f"  ⏰ Period end: {period_end}, Now: {now}")
    else:
        logger.warning(f"  ⚠️ No current_period_end found in subscription")
    
    # 5️⃣ Calculate expected proration
    expected_prorated = 0.0
    
    if days_remaining > 0:
        price_difference = new_price - current_price
        logger.debug(f"  💰 Price difference: ${price_difference:.2f}")
        
        if price_difference <= 0:
            logger.warning(f"  ⚠️ Price difference is ${price_difference:.2f} - this is not an upgrade!")
            # Continue anyway for debugging
        
        # Calculate using exact days for more accuracy
        exact_days = (period_end - now).total_seconds() / (24 * 3600) if current_sub.current_period_end else days_remaining
        exact_prorated = price_difference * (exact_days / 30)
        expected_prorated = max(exact_prorated, 0)  # Don't go negative
        
        logger.info(f"  🧮 Proration calculation:")
        logger.info(f"    Monthly difference: ${price_difference:.2f}")
        logger.info(f"    Days remaining: {exact_days:.2f} / 30 = {exact_days/30:.3f}")
        logger.info(f"    Expected prorated: ${expected_prorated:.2f}")
        
        # Alternative calculation for verification
        unused_current = current_price * (exact_days / 30)
        charge_for_remaining = new_price * (exact_days / 30)
        net_prorated = charge_for_remaining - unused_current
        
        logger.debug(f"Verification calculation:")
        logger.debug(f"    Unused current plan value: ${unused_current:.2f}")
        logger.debug(f"    New plan charge for remaining: ${charge_for_remaining:.2f}")
        logger.debug(f"    Net prorated (verification): ${net_prorated:.2f}")
    else:
        logger.info(f"  📊 No proration applicable (days_remaining: {days_remaining})")
    
    # 6️⃣ Polar checkout preparation
    logger.info(f"🛒 5. Preparing Polar checkout payload for subscription {current_sub.polar_subscription_id}")
    
  
    
    checkout_payload = {
        "subscription": current_sub.polar_subscription_id,
        "products": [polar_product_id],
        "proration_behavior": "create_prorations",  # Charges $7.77 today
        "success_url": f"{get_settings().frontend_url}/subscription?upgrade=success",
        "cancel_url": f"{get_settings().frontend_url}/subscription?upgrade=cancelled",
   "metadata": {
        "user_id": user_id,
        # These help Polar but don't control formatting
        "current_plan_name": current_sub.plan.name,
         "action": "upgrade_immediate",
        "new_plan_name": new_plan.name,
        "expected_prorated": expected_prorated
        
    },
    "automatic_tax": {"enabled": True}
    }


    
    
    logger.debug(f"📦 Checkout payload:")
    logger.debug(f"  subscription: {current_sub.polar_subscription_id}")
    logger.debug(f"  products: {[polar_product_id]}")
    # logger.debug(f"  metadata: {payload_metadata}")
    
    # 7️⃣ Polar API call
    logger.info(f"📡 6. Calling Polar API to create checkout")
    
    def _create_checkout():
        try:
            logger.debug(f"  🧵 Threadpool: Starting Polar API call")
            with get_polar_client() as polar:
                logger.debug(f"  🔗 Polar client initialized")
                
                # Log the exact payload being sent
                import json
                logger.debug(f"  📤 Sending payload to Polar: {json.dumps(checkout_payload, default=str)}")
                
                result = polar.checkouts.create(request=checkout_payload)
                
                logger.debug(f"  📥 Polar API response received")
                logger.debug(f"  Response type: {type(result)}")
                logger.debug(f"  Response attributes: {[attr for attr in dir(result) if not attr.startswith('_')][:10]}")
                
                # Try to get more details
                if hasattr(result, 'id'):
                    logger.info(f"  ✅ Checkout created: ID={result.id}")
                if hasattr(result, 'url'):
                    logger.info(f"  🔗 Checkout URL: {result.url}")
                
                return result
        except Exception as e:
            logger.error(f"  ❌ Polar API call failed: {str(e)}")
            logger.error(f"  📝 Error type: {type(e).__name__}")
          
            logger.error(f"  🔍 Traceback:\n{traceback.format_exc()}")
            raise
    
    try:
        logger.debug(f"⚡ Starting run_in_threadpool for Polar API")
        checkout_session = await run_in_threadpool(_create_checkout)
        
        logger.info(f"🎉 SUCCESS: Checkout created successfully")
        logger.info(f"   URL: {checkout_session.url}")
        
        # Build response
        response_data = {
            "success": True,
            "checkout_url": checkout_session.url,
            "display_details": {
                "message": "You'll only pay the prorated amount today",
                "expected_today_charge": round(expected_prorated, 2),
                "next_full_charge": new_price,
                "next_billing_date": period_end_iso,
                "current_plan": current_sub.plan.name,
                "new_plan": new_plan.name,
                "days_remaining": days_remaining,
                "debug": {
                    "current_price": current_price,
                    "new_price": new_price,
                    "price_difference": round(new_price - current_price, 2),
                    "calculation": f"${new_price - current_price:.2f} × ({days_remaining}/30)",
                    "timestamp": now.isoformat()
                }
            },
            "debug_info": {
                "subscription_id": current_sub.polar_subscription_id,
                "user_id": user_id,
                
                "product_id": polar_product_id,
                "checkout_created_at": now.isoformat()
            }
        }
        
        logger.debug(f"📤 Returning response: {json.dumps(response_data, default=str)}")
        return response_data
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"💥 CHECKOUT CREATION FAILED: {error_msg}")
        
        # Analyze the error
        if "already has an active subscription" in error_msg.lower():
            logger.error("🔍 ANALYSIS: Polar thinks we're creating a NEW subscription, not upgrading")
            logger.error("💡 TROUBLESHOOTING: Check if 'subscription' parameter is being sent correctly")
            raise HTTPException(
                status_code=400,
                detail="Upgrade failed. Polar attempted to create a new subscription instead of upgrading. Please check the 'subscription' parameter."
            )
        elif "subscription" in error_msg.lower() and "not found" in error_msg.lower():
            logger.error("🔍 ANALYSIS: Polar subscription ID not found or invalid")
            logger.error(f"💡 TROUBLESHOOTING: Verify subscription ID: {current_sub.polar_subscription_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Subscription ID not found in Polar. Please verify your subscription: {current_sub.polar_subscription_id}"
            )
        else:
            logger.error(f"🔍 ANALYSIS: Unknown error - {error_msg}")
            raise HTTPException(
                status_code=400,
                detail=f"Checkout creation failed: {error_msg}"
            )




# Optional: Add a debug endpoint to test specific scenarios
@router.get("/debug/upgrade-test")
async def debug_upgrade_test(
    user_id: str,
    polar_product_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Debug endpoint to test upgrade logic without creating checkout.
    """
    logger.info(f"🔧 DEBUG ENDPOINT CALLED - user_id: {user_id}, product_id: {polar_product_id}")
    
    # Run the same logic but stop before Polar API call
    # ... (copy logic from create_verified_upgrade_checkouts but stop at step 6)
    
    return {
        "debug_mode": True,
        "user_id": user_id,
        "product_id": polar_product_id,
        "test_completed": True,
        "note": "This is a debug endpoint - no checkout created"
    }



@router.post("/upgrade")
async def upgrade_subscription(
    user_id: str = Body(..., embed=True), # In real auth, this comes from current_user
    new_polar_plan_id: str = Body(..., embed=True),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Upgrade subscription to a new plan (immediate patch).
    """
    try:
        result = await upgrade_subscription(
            session=session,
            user_id=user_id,
            new_plan_polar_id=new_polar_plan_id
        )
        return SuccessResponse(message=result["message"], data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel")
async def cancel_subscription(
 user_id: str = Body(...),
 subscription_id: str = Body(...),
 session: AsyncSession = Depends(get_db_session)
):
    """
    Cancel subscription.
    """
    try:
        result = await cancel_user_subscription(
            session=session,
            user_id=user_id,
            subscription_id=subscription_id
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# DOWNGRADE ENDPOINTS
# ============================================================================

@router.get("/downgrade/preview")
async def preview_downgrade(
    polar_product_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Preview downgrade cost with proration breakdown.
    
    Shows:
    - Current plan details
    - New plan details
    - Credit from unused portion of current plan
    - Charge for new plan's prorated period
    - Net amount (credit or charge)
    - Next billing date
    
    This is for display purposes only - actual proration is handled by Polar.
    """
    try:
        preview = await calculate_downgrade_proration(
            session=session,
            user_id=user_id,
            polar_product_id=polar_product_id
        )
        
        if "error" in preview:
            raise HTTPException(
                status_code=400,
                detail=preview["error"]
            )
        
        return SuccessResponse(
            message="Downgrade preview calculated",
            data=preview
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview downgrade error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/downgrade/checkout")
async def downgrade_subscription_endpoint(
    polar_product_id: str = Body(..., embed=True),
    user_id: str = Body(..., embed=True),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Downgrade subscription to a lower-tier plan immediately.
    
    This endpoint:
    1. Validates the downgrade (ensures new plan is cheaper)
    2. Archives current subscription to history
    3. Updates subscription via Polar API with proration
    4. Updates local database with new plan
    
    Polar will automatically:
    - Credit unused portion of current plan
    - Charge prorated amount for new plan
    - Apply net credit/charge to account
    """
    try:
        result = await downgrade_subscription(
            session=session,
            user_id=user_id,
            new_plan_polar_id=polar_product_id
        )
        
        return SuccessResponse(
            message=result.get("message", "Downgrade successful"),
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Downgrade error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# SUBSCRIPTION DATA ENDPOINTS
# ============================================================================

@router.get("/me")
async def get_my_subscription(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get the current user's active subscription details.
    """
    try:
        # Query for user's active subscription with plan details
        stmt = (
            select(Subscription, Plan)
            .join(Plan, Subscription.plan_id == Plan.id)
            .where(
                Subscription.user_id == current_user.id
            )
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        
        result = await session.execute(stmt)
        subscription_plan = result.first()
        
        if not subscription_plan:
            return {
                "subscription": None,
                "message": "No active subscription found"
            }
        
        subscription, plan = subscription_plan
        
        return {
            "subscription": {
                "id": str(subscription.id),
                "user_id": str(subscription.user_id),
                "plan_id": str(subscription.plan_id),
                "polar_subscription_id": subscription.polar_subscription_id,
                "status": subscription.status.value if hasattr(subscription.status, 'value') else subscription.status,
                "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "canceled_at": subscription.canceled_at.isoformat() if subscription.canceled_at else None,
                "ended_at": subscription.ended_at.isoformat() if subscription.ended_at else None,
                "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
                "updated_at": subscription.updated_at.isoformat() if subscription.updated_at else None,
            },
            "plan": {
                "id": str(plan.id),
                "name": plan.name,
                "plan_type": plan.plan_type.value if hasattr(plan.plan_type, 'value') else plan.plan_type,
                "polar_plan_id": plan.polar_plan_id,
                "chat_limit": plan.chat_limit,
                "card_limit": plan.card_limit,
                "max_meditation_duration": plan.max_meditation_duration,
                "is_audio": plan.is_audio,
                "is_video": plan.is_video,
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching user subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch subscription: {str(e)}")


@router.get("/")
async def get_all_subscriptions(
    session: AsyncSession = Depends(get_db_session),
    skip: int = 0,
    limit: int = 100
):
    """
    Get all subscriptions (admin endpoint - consider adding auth check).
    """
    try:
        # Query all subscriptions with plan details
        stmt = (
            select(Subscription, Plan, UserProfile)
            .join(Plan, Subscription.plan_id == Plan.id)
            .join(UserProfile, Subscription.user_id == UserProfile.id)
            .order_by(Subscription.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        subscriptions_data = result.all()
        
        subscriptions_list = []
        for subscription, plan, user in subscriptions_data:
            subscriptions_list.append({
                "subscription": {
                    "id": str(subscription.id),
                    "user_id": str(subscription.user_id),
                    "plan_id": str(subscription.plan_id),
                    "polar_subscription_id": subscription.polar_subscription_id,
                    "status": subscription.status.value if hasattr(subscription.status, 'value') else subscription.status,
                    "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                    "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                    "cancel_at_period_end": subscription.cancel_at_period_end,
                    "canceled_at": subscription.canceled_at.isoformat() if subscription.canceled_at else None,
                    "ended_at": subscription.ended_at.isoformat() if subscription.ended_at else None,
                    "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
                    "updated_at": subscription.updated_at.isoformat() if subscription.updated_at else None,
                },
                "plan": {
                    "id": str(plan.id),
                    "name": plan.name,
                    "plan_type": plan.plan_type.value if hasattr(plan.plan_type, 'value') else plan.plan_type,
                    "polar_plan_id": plan.polar_plan_id,
                },
                "user": {
                    "id": str(user.id),
                    "name": user.name,
                    "email": user.email_id,
                    "plan_type": user.plan_type.value if hasattr(user.plan_type, 'value') else user.plan_type,
                }
            })
        
        return {
            "subscriptions": subscriptions_list,
            "count": len(subscriptions_list),
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching all subscriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch subscriptions: {str(e)}")


@router.post("/revoke")
async def revoke_subscription(
    user_id: str = Body(..., embed=True),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Revoke subscription immediately.
    """
    try:
        # Currently same logic as cancel
        result = await revoke_subscription(
            session=session,
            user_id=user_id
        )
        return SuccessResponse(message=result["message"], data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def ensure_utc(dt):
    """Ensure datetime is timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def extract_price_from_plan(plan: Plan) -> float:
    """
    Reliably extract price from a Plan's prices relationship.
    Checks multiple possible field names.
    """
    if not plan or not plan.prices:
        print(f"⚠️ No prices found for plan {plan.name if plan else 'None'}")
        return 0.0

    print(f"🔍 Extracting price from plan: {plan.name}")
    print(f"📦 Plan has {len(plan.prices)} price object(s)")

    for i, price_obj in enumerate(plan.prices):
        print(f"  Price {i}: {type(price_obj).__name__}")
        
        # Try common field names in order of likelihood
        for field_name in ['price', 'amount', 'unit_amount', 'monthly_price', 'price_amount']:
            if hasattr(price_obj, field_name):
                value = getattr(price_obj, field_name)
                print(f"    Found field '{field_name}': {value} (type: {type(value)})")
                
                if value is not None:
                    try:
                        price_float = float(value)
                        if price_float > 0:
                            print(f"✅ Extracted price: ${price_float:.2f}")
                            return price_float
                    except (ValueError, TypeError) as e:
                        print(f"    ⚠️ Could not convert {value} to float: {e}")
                        continue

    print(f"❌ No valid price found for plan {plan.name}")
    return 0.0


def get_polar_price_id(plan: Plan) -> str | None:
    """
    Extract Polar price ID from plan.
    Checks prices relationship and plan attributes.
    """
    print(f"🔍 Getting Polar price ID for plan: {plan.name}")
    
    # First check if plan has prices with Polar IDs
    if plan.prices:
        for price_obj in plan.prices:
            for field in ['polar_price_id', 'price_id', 'id', 'polar_id', 'external_id']:
                if hasattr(price_obj, field):
                    price_id = getattr(price_obj, field)
                    if price_id:
                        print(f"✅ Found price ID in prices.{field}: {price_id}")
                        return str(price_id)
    
    # Check plan-level attributes
    for field in ['polar_price_id', 'default_price_id', 'price_id']:
        if hasattr(plan, field):
            price_id = getattr(plan, field)
            if price_id:
                print(f"✅ Found price ID in plan.{field}: {price_id}")
                return str(price_id)
    
    print(f"❌ No Polar price ID found for plan {plan.name}")
    return None



async def calculate_detailed_proration(
    session: AsyncSession,
    user_id: str,
    polar_product_id: str
) -> dict:
    """
    Calculate and return detailed proration information for display.
    This is for preview purposes only - actual proration is handled by Polar.
    """
    
    print(f"\n{'='*80}")
    print(f"💰 CALCULATE PRORATION PREVIEW")
    print(f"   User: {user_id}")
    print(f"   Target Product: {polar_product_id}")
    print(f"{'='*80}\n")
    
    # Load current subscription
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        .options(
            selectinload(Subscription.plan)
            .selectinload(Plan.prices)
        )
    )
    
    result = await session.execute(stmt)
    current_sub = result.scalar_one_or_none()
    
    if not current_sub or not current_sub.plan:
        return {"error": "No active subscription found"}
    
    # Load target plan
    plan_stmt = (
        select(Plan)
        .where(Plan.polar_plan_id == polar_product_id)
        .options(selectinload(Plan.prices))
    )
    
    plan_result = await session.execute(plan_stmt)
    new_plan = plan_result.scalar_one_or_none()
    
    if not new_plan:
        return {"error": "Target plan not found"}
    
    # Extract prices
    current_price = extract_price_from_plan(current_sub.plan)
    new_price = extract_price_from_plan(new_plan)
    price_difference = new_price - current_price
    
    # Time calculations
    now = datetime.now(timezone.utc)
    period_end = ensure_utc(current_sub.current_period_end)
    
    response = {
        "current_plan": current_sub.plan.name,
        "new_plan": new_plan.name,
        "current_monthly_price": current_price,
        "new_monthly_price": new_price,
        "monthly_price_difference": round(price_difference, 2),
        "proration_applicable": False,
        "prorated_amount": 0.0,
        "days_remaining": 0,
    }
    
    # If no billing period info
    if not period_end or period_end <= now:
        response["note"] = "Billing period ended or unavailable. Will start new cycle immediately."
        return response
    
    # Calculate days remaining
    seconds_remaining = (period_end - now).total_seconds()
    days_remaining = seconds_remaining / 86400
    
    if days_remaining <= 0:
        return response
    
    # Billing cycle length
    billing_cycle_days = 30  # default
    cycle = str(getattr(current_sub.plan, "billing_cycle", "")).lower()
    if "year" in cycle:
        billing_cycle_days = 365
    elif "week" in cycle:
        billing_cycle_days = 7
    
    # Calculate proration
    current_daily = current_price / billing_cycle_days
    new_daily = new_price / billing_cycle_days
    daily_diff = new_daily - current_daily
    old_price_value = current_daily * days_remaining
    new_price_value = new_daily * days_remaining
    prorated_amount = new_price - old_price_value
    final_amount = max(0, prorated_amount)  # Don't show negative for downgrades
    
    response.update({
        "proration_applicable": True,
        "prorated_amount": round(final_amount, 2),
        "days_remaining": round(days_remaining, 1),
        "daily_rate_difference": round(daily_diff, 4),
        "next_full_billing": period_end.isoformat(),
        "breakdown": [
            {
                "description": "Unused portion of current plan",
                "amount": round(current_price * (days_remaining / billing_cycle_days), 2),
            },
            {
                "description": "New plan for remaining days",
                "amount": round(new_price , 2),
            },
            {
                "description": "Net prorated charge today",
                "amount": round(prorated_amount, 2),
                "is_total": True,
            },
        ],
    })
    
    print("✅ Proration preview calculated:")
    print(f"   Days remaining: {days_remaining:.1f}")
    print(f"   Prorated amount: ${final_amount:.2f}")
    
    return response


# ========================================================================
# UPGRADE CHECKOUT CREATION (Alternative Approach)
# ========================================================================

async def create_auto_upgrade_checkout(
    session: AsyncSession,
    user_id: str,
    polar_product_id: str
) -> dict:
    """
    Automatic upgrade with proration calculation for display.
    This is what the frontend should call for upgrades.
    """
    print(f"\n{'='*80}")
    print(f"🔄 AUTO UPGRADE CHECKOUT")
    print(f"   User: {user_id}")
    print(f"   Polar Product ID: {polar_product_id}")
    print(f"{'='*80}\n")
    
    # 1. Get current subscription
    print("📋 Loading current subscription...")
    
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        .options(
            selectinload(Subscription.plan)
            .selectinload(Plan.prices)
        )
    )
    
    result = await session.execute(stmt)
    current_sub = result.scalar_one_or_none()
    
    if not current_sub:
        raise HTTPException(
            status_code=400,
            detail="No active subscription found"
        )
    
    if not current_sub.polar_subscription_id:
        raise HTTPException(
            status_code=400,
            detail="Subscription missing Polar ID"
        )
    
    # 2. Get new plan
    print("📋 Loading target plan...")
    
    plan_stmt = (
        select(Plan)
        .where(Plan.polar_plan_id == polar_product_id)
        .options(selectinload(Plan.prices))
    )
    
    plan_result = await session.execute(plan_stmt)
    new_plan = plan_result.scalar_one_or_none()
    
    if not new_plan:
        raise HTTPException(
            status_code=404,
            detail="Plan not found"
        )
    
    # 3. Calculate proration for display
    print("🧮 Calculating proration...")
    
    current_price = extract_price_from_plan(current_sub.plan)
    new_price = extract_price_from_plan(new_plan)
    
    if new_price <= current_price:
        raise HTTPException(
            status_code=400,
            detail="This is not an upgrade (price is lower or equal)"
        )
    
    now = datetime.now(timezone.utc)
    period_end = ensure_utc(current_sub.current_period_end)
    
    days_remaining = 0
    expected_prorated = 0.0
    
    if period_end and period_end > now:
        days_remaining = (period_end - now).days
        price_diff = new_price - current_price
        expected_prorated = price_diff * (days_remaining / 30)
        expected_prorated = max(expected_prorated, 0)
    
    # 4. Create checkout
    print("🛒 Creating checkout...")
    
    settings = get_settings()
    
    def _create_checkout():
        with get_polar_client() as polar:
            checkout_payload = {
                "subscription": current_sub.polar_subscription_id,
                "products": [polar_product_id],
                "success_url": f"{settings.frontend_url}/subscription?upgrade=success",
                "metadata": {
                    "user_id": user_id,
                    "action": "upgrade",
                    "from_plan": str(current_sub.plan_id),
                    "to_plan": str(new_plan.id),
                    "expected_prorated": str(round(expected_prorated, 2)),
                    "days_remaining": str(days_remaining)
                }
            }
            
            print(f"📤 Checkout payload:")
            print(f"   subscription: {current_sub.polar_subscription_id}")
            print(f"   products: [{polar_product_id}]")
            
            try:
                session_obj = polar.checkouts.create(request=checkout_payload)
                print(f"✅ Checkout created: {session_obj.url}")
                return session_obj
            except Exception as e:
                print(f"❌ Checkout error: {str(e)}")
                raise
    
    try:
        checkout_session = await run_in_threadpool(_create_checkout)
        
        return {
            "success": True,
            "checkout_url": checkout_session.url,
            "display_details": {
                "message": "You'll only pay the prorated amount today",
                "expected_today_charge": round(expected_prorated, 2),
                "next_full_charge": new_price,
                "current_plan": current_sub.plan.name,
                "new_plan": new_plan.name,
                "days_remaining": days_remaining,
                "next_billing_date": period_end.isoformat() if period_end else None,
                "billing_note": "Your subscription will automatically renew at the new rate after this billing period."
            }
        }
        
    except Exception as e:
        error_msg = str(e)
        if "already has an active subscription" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="Unable to create upgrade checkout. Please contact support."
            )
        raise HTTPException(
            status_code=400,
            detail=f"Checkout creation failed: {error_msg}"
        )


async def direct_subscription_upgrade(
    session: AsyncSession,
    user_id: str,
    polar_product_id: str,
    prorate: bool = True  # Add proration parameter
) -> dict:
    """
    Directly upgrade subscription via Polar API.
    No checkout flow - immediate upgrade.
    """
    print(f"\n{'='*80}")
    print(f"⚡ DIRECT SUBSCRIPTION UPGRADE")
    print(f"   User: {user_id}")
    print(f"   Polar Product ID: {polar_product_id}")
    print(f"   Prorate: {prorate}")
    print(f"{'='*80}\n")
    
    # 1. Get current subscription
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        .options(
            selectinload(Subscription.plan)
            .selectinload(Plan.prices)
        )
    )
    
    result = await session.execute(stmt)
    current_sub = result.scalar_one_or_none()
    
    if not current_sub:
        raise HTTPException(
            status_code=400,
            detail="No active subscription found"
        )
    
    if not current_sub.polar_subscription_id:
        raise HTTPException(
            status_code=400,
            detail="Subscription missing Polar ID"
        )
    
    # 2. Get new plan
    plan_stmt = (
        select(Plan)
        .where(Plan.polar_plan_id == polar_product_id)
        .options(selectinload(Plan.prices))
    )
    
    plan_result = await session.execute(plan_stmt)
    new_plan = plan_result.scalar_one_or_none()
    
    if not new_plan:
        raise HTTPException(
            status_code=404,
            detail="Plan not found"
        )
    
    # 3. Get Polar price ID
    new_price_id = get_polar_price_id(new_plan)
    
    if not new_price_id:
        raise HTTPException(
            status_code=400,
            detail="Target plan is missing price configuration"
        )
    
    # 4. Calculate proration for display
    current_price = extract_price_from_plan(current_sub.plan)
    new_price = extract_price_from_plan(new_plan)
    
    if new_price <= current_price:
        raise HTTPException(
            status_code=400,
            detail="This is not an upgrade (price is lower or equal)"
        )
    
    now = datetime.now(timezone.utc)
    period_end = ensure_utc(current_sub.current_period_end)
    
    days_remaining = 0
    expected_prorated = 0.0
    
    if period_end and period_end > now:
        days_remaining = (period_end - now).days
        price_diff = new_price - current_price
        expected_prorated = price_diff * (days_remaining / 30)
        expected_prorated = max(expected_prorated, 0)
    
    print(f"💰 Price change: ${current_price:.2f} → ${new_price:.2f}")
    print(f"📅 Days remaining: {days_remaining}")
    print(f"🧮 Expected prorated charge: ${expected_prorated:.2f}")
    
    # 5. Set proration behavior
    if prorate:
        proration_behavior = "always_invoice"  # Charge prorated amount immediately
        print("✅ Proration: ENABLED (will charge prorated amount now)")
    else:
        proration_behavior = "none"  # No immediate charge, apply at next billing cycle
        expected_prorated = 0.0  # No charge today
        print("Proration: DISABLED (will charge full amount next cycle)")
    
    # 6. Direct Polar API call to upgrade
    print("⚡ Calling Polar API for direct upgrade...")
    
    def _direct_upgrade():
        with get_polar_client() as polar:
            print(f"📤 Updating subscription {current_sub.polar_subscription_id}")
            print(f"📤 New price ID: {new_price_id}")
            print(f"📤 Proration behavior: {proration_behavior}")
            
            try:
                # Try direct subscription update
                update_params = {
                    "id": current_sub.polar_subscription_id,
                    "price_id": new_price_id
                }
                
                # Add proration behavior if specified
                if proration_behavior:
                    update_params["proration_behavior"] = proration_behavior
                
                updated_sub = polar.subscriptions.update(**update_params)
                
                print(f"✅ Direct upgrade successful: {updated_sub.id}")
                print(f"📅 New period end: {getattr(updated_sub, 'current_period_end', 'N/A')}")
                print(f"💰 New status: {getattr(updated_sub, 'status', 'N/A')}")
                print(f"💳 Invoice status: {getattr(updated_sub, 'latest_invoice', 'N/A')}")
                
                # Check if invoice was created
                if hasattr(updated_sub, 'latest_invoice'):
                    invoice = updated_sub.latest_invoice
                    if hasattr(invoice, 'amount_due'):
                        print(f"💵 Amount due: ${invoice.amount_due/100:.2f}")
                
                return updated_sub
                
            except Exception as e:
                print(f"❌ Direct upgrade failed: {str(e)}")
                
                # Fall back to checkout flow
                print("🔄 Falling back to checkout flow...")
                settings = get_settings()
                
                checkout_payload = {
                    "subscription": current_sub.polar_subscription_id,
                    "products": [polar_product_id],
                    "success_url": f"{settings.frontend_url}/subscription?upgrade=success",
                    "metadata": {
                        "user_id": user_id,
                        "action": "upgrade",
                        "from_plan": str(current_sub.plan_id),
                        "to_plan": str(new_plan.id),
                        "expected_prorated": str(round(expected_prorated, 2)),
                        "prorate": str(prorate)
                    }
                }
                
                session_obj = polar.checkouts.create(request=checkout_payload)
                print(f"🛒 Checkout created as fallback: {session_obj.url}")
                
                return {"checkout_url": session_obj.url, "type": "checkout_fallback"}
    
    try:
        polar_response = await run_in_threadpool(_direct_upgrade)
        
        # Check if we got a checkout URL (fallback)
        if isinstance(polar_response, dict) and "checkout_url" in polar_response:
            return {
                "success": True,
                "requires_checkout": True,
                "checkout_url": polar_response["checkout_url"],
                "message": "Please complete checkout to upgrade",
                "upgrade_details": {
                    "current_plan": current_sub.plan.name,
                    "new_plan": new_plan.name,
                    "expected_today_charge": round(expected_prorated, 2),
                    "days_remaining": days_remaining,
                    "next_billing_date": period_end.isoformat() if period_end else None,
                    "proration_enabled": prorate
                }
            }
        
        # Direct upgrade was successful
        # Update local database
        current_sub.plan_id = new_plan.id
        
        # Update period end if available
        if hasattr(polar_response, 'current_period_end'):
            current_sub.current_period_end = polar_response.current_period_end
            print(f"📅 Updated period end to: {current_sub.current_period_end}")
        
        current_sub.updated_at = datetime.utcnow()
        session.add(current_sub)
        
        # Update user's plan type
        user_stmt = select(UserProfile).where(UserProfile.id == user_id)
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        
        if user:
            user.plan_type = new_plan.plan_type
            session.add(user)
            print(f"👤 Updated user plan type to: {new_plan.plan_type}")
        
        await session.commit()
        
        print("✅ Database updated successfully")
        
        # Determine actual charge
        actual_charge = expected_prorated if prorate else 0.0
        
        return {
            "success": True,
            "requires_checkout": False,
            "message": f"Successfully upgraded to {new_plan.name}",
            "upgrade_details": {
                "new_plan": new_plan.name,
                "new_price": new_price,
                "proration_enabled": prorate,
                "charged_today": round(actual_charge, 2),
                "next_billing_date": period_end.isoformat() if period_end else None,
                "next_full_charge": new_price,
                "current_plan": current_sub.plan.name,
                "current_price": current_price,
                "days_remaining": days_remaining
            }
        }
        
    except Exception as e:
        await session.rollback()
        
        error_msg = str(e)
        print(f"❌ Upgrade failed: {error_msg}")
        
        # Provide helpful error messages
        if "cannot be updated to a plan of a different interval" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="Cannot change billing interval. Please contact support."
            )
        elif "price" in error_msg.lower() and "not found" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="Invalid price configuration. Please contact support."
            )
        elif "proration_behavior" in error_msg.lower():
            raise HTTPException(
                status_code=400,
                detail=f"Proration setting error: {error_msg}"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Upgrade failed: {error_msg}"
            )



async def upgrade_subscription(
        session: AsyncSession,
        user_id: str,
        new_plan_polar_id: str
    ) -> dict:
        """
        Upgrades a user's subscription to a new plan using Polar's generic update (patch).
        
        Logic:
        1. Find current active subscription.
        2. Find new plan details.
        3. Archive current subscription state to SubscriptionHistory.
        4. Call Polar API to update (patch) the subscription with new price_id.
        5. Update local subscription record to reflect new plan.
        """
        print(f"DEBUG V1: Upgrade requested for user {user_id} to plan {new_plan_polar_id}")
        
        # 1. Get current active subscription
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).options(
            selectinload(Subscription.plan)
        )
        result = await session.execute(stmt)
        current_sub = result.scalar_one_or_none()
        
        if not current_sub:
             raise HTTPException(status_code=400, detail="No active subscription found to upgrade.")
             
        # 2. Get new plan details
        plan_stmt = select(Plan).where(Plan.polar_plan_id == new_plan_polar_id).options(selectinload(Plan.prices))
        plan_result = await session.execute(plan_stmt)
        new_plan = plan_result.scalar_one_or_none()
        
        if not new_plan:
            raise HTTPException(status_code=404, detail="New plan not found.")
            
        if current_sub.plan_id == new_plan.id:
             return {"success": False, "message": "Already on this plan."}

        # Find new price ID (Polar Price ID)
        new_polar_price_id = None
        if new_plan.prices:
            for price in new_plan.prices:
                if price.polar_price_id:
                    new_polar_price_id = price.polar_price_id
                    break
        
        if not new_polar_price_id:
             # Fallback: check plan metadata or throw error
             # Some setups might store it differently
             raise HTTPException(status_code=400, detail="Price ID for new plan not found.")

        print(f"DEBUG V1: Upgrading from {current_sub.plan.name} to {new_plan.name}")
        
        # 3. Archive to SubscriptionHistory
        # history_entry = SubscriptionHistory(
        #     subscription_id=current_sub.id,
        #     previous_plan_id=current_sub.plan_id,
        #     polar_subscription_id=current_sub.polar_subscription_id,
        #     status=current_sub.status,
        #     user_id=user_id,
        #     created_at=datetime.utcnow()
        # )
        # session.add(history_entry)
        
        # 4. Call Polar API
        def _call_polar_update():
            with get_polar_client() as polar:
                # https://docs.polar.sh/api/v1/subscriptions/update
                # Using 'always_invoice' to trigger immediate charge/proration if configured
                return polar.subscriptions.update(
                    id=current_sub.polar_subscription_id,
                    subscription_update={
                        "product_id": new_plan_polar_id,
                        "proration_behavior": "invoice"
                    }
                )
        
        try:
            polar_updated_sub =await run_in_threadpool(_call_polar_update)
            print(f"DEBUG V1: Polar update successful: {polar_updated_sub.id}")
        except Exception as e:
            await session.rollback()
            print(f"ERROR V1: Polar update failed: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to upgrade subscription with provider: {str(e)}")

        # 5. Update local subscription and user
        current_sub.plan_id = new_plan.id
        current_sub.updated_at = datetime.utcnow()
        
        # Determine plan type for user profile
        user_stmt = select(UserProfile).where(UserProfile.id == user_id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        
        if user:
            user.plan_type = new_plan.plan_type
            session.add(user)
            
        session.add(current_sub)
        await session.commit()
        
        return {
            "success": True,
            "message": f"Successfully upgraded to {new_plan.name}",
            "new_plan": new_plan.name,
            "plan_type": new_plan.plan_type.value
        }




async def cancel_subscription(
        session: AsyncSession,
        user_id: str
    ) -> dict:
        """
        Cancels the user's active subscription.
        """
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        result = await session.execute(stmt)
        current_sub = result.scalar_one_or_none()
        
        if not current_sub:
            raise HTTPException(status_code=400, detail="No active subscription to cancel.")
            
        def _call_polar_cancel():
            with get_polar_client() as polar:
                return polar.subscriptions.cancel(id=current_sub.polar_subscription_id)
                
        try:
            await run_in_threadpool(_call_polar_cancel)
        except Exception as e:
             # Even if Polar fails (e.g. already canceled), we might want to update local state or warn
             print(f"ERROR V1: Polar cancel failed: {e}")
             raise HTTPException(status_code=400, detail=f"Failed to cancel subscription: {str(e)}")
             
        # Update local state
        # Usually canceling sets cancel_at_period_end=True in Polar
        # But for 'immediate' effect request, we might want to mark it CANCELED locally or wait for webhook
        # User request: "3.1 SystemAction : Create the end point for that. also handle all the necessary action for the plan and usage"
        
        # We'll mark it as CANCELED immediately if that's the desired behavior, 
        # OR we just update the status to indicate cancellation is pending.
        # Standard practice: Mark as CANCELED if it's immediate, or keep ACTIVE but set cancel_at_period_end.
        # Let's start by setting status to CANCELED to be safe/clear per user request "Subscription Cancel".
        
        current_sub.status = SubscriptionStatus.CANCELED
        current_sub.ended_at = datetime.utcnow()
        session.add(current_sub)
        
        # Downgrade user to Basic/Free immediately? 
        # Or wait for period end? User asked "handle all necessary action for plan and usage".
        # Safe bet: Downgrade immediately if we are canceling immediately.
        user_stmt = select(UserProfile).where(UserProfile.id == user_id)
        user_res = await session.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if user:
            user.plan_type = PlanType.BASIC # Fallback to basic
            session.add(user)
            
        await session.commit()
        
        return {"success": True, "message": "Subscription canceled."}




async def revoke_subscription(
        session: AsyncSession,
        user_id: str
    ) -> dict:
        """
        Revokes subscription immediately (similar to cancel but maybe more aggressive or different semantic).
        User request: "Inactive the curuent plant"
        """
        # Reuse cancel logic but maybe ensuring it's immediate revocation
        # Polar 'cancel' usually just stops renewal. 'revoke' might be distinct in some APIs,
        # but Polar Python SDK mainly has 'cancel'.
        # We will treat this as immediate hard cancellation.
        return await SubscriptionServiceV1.cancel_subscription(session, user_id)


# ============================================================================
# RAZORPAY ENDPOINTS  (Indian payment gateway)
# ============================================================================

@router.post("/razorpay-checkout")
async def create_razorpay_checkout(
    plan_id: int = Query(..., description="Internal DB plan ID"),
    user_id: str = Query(..., description="User UUID"),
    redirect_url: str = Query(None, description="URL to redirect after payment"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Create a Razorpay subscription checkout for Indian users.
    Returns {"checkout_url": "https://rzp.io/..."} — redirect the user there.

    Pre-conditions (enforced by startup migration):
      - Plan must exist in DB with razorpay_plan_id populated.
      - ASAM_RAZORPAY_KEY_ID and ASAM_RAZORPAY_KEY_SECRET must be valid ASCII.
    """
    from src.razorpayservice.razorpay_client import is_razorpay_enabled
    from src.razorpayservice.razorpay_service import RazorpayService, INR_PLAN_CONFIG

    # 1. Gateway availability check
    if not is_razorpay_enabled():
        raise HTTPException(
            status_code=503,
            detail="INR payment gateway is not available. Please contact support.",
        )

    # 2. Load and validate plan
    plan = (await session.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")

    if not plan.razorpay_plan_id:
        logger.error(
            "[RAZORPAY] Plan '%s' (id=%d) has no razorpay_plan_id — "
            "startup migration may have failed. Check ASAM_RAZORPAY_KEY_ID credential.",
            plan.name, plan_id,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "INR billing is not yet configured for this plan. "
                "Please contact support — this is a one-time setup issue."
            ),
        )

    cfg_key = (plan.plan_type, plan.billing_cycle)
    if cfg_key not in INR_PLAN_CONFIG:
        raise HTTPException(status_code=400, detail="Plan type not supported for INR billing.")

    # 3. Load and validate user
    user = (await session.execute(
        select(UserProfile).where(UserProfile.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if not user.email_id:
        raise HTTPException(status_code=400, detail="Account is missing an email address.")

    # 4. Build checkout
    settings = get_settings()
    success_url = redirect_url or f"{settings.frontend_url}/subscription?upgrade=success"
    total_count = INR_PLAN_CONFIG[cfg_key]["total_count"]

    try:
        svc = RazorpayService()
        result = await run_in_threadpool(
            svc.create_subscription,
            plan.razorpay_plan_id,
            str(user.id),
            user.email_id,
            total_count,
            success_url,   # callback_url — Razorpay redirects here after payment
        )
    except ValueError as exc:
        # Credential or config problem — clear message for operator
        logger.error("[RAZORPAY] Credential/config error in checkout: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Payment gateway configuration error: {exc}",
        )
    except Exception as exc:
        logger.error("[RAZORPAY] Checkout error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="Payment gateway returned an error. Please try again in a moment.",
        )

    logger.info(
        "[RAZORPAY] Checkout created: plan=%s subscription=%s user=%s",
        plan.name, result["subscription_id"], user_id,
    )
    return SuccessResponse(
        message="Razorpay checkout created",
        data={
            "checkout_url": result["short_url"],
            "subscription_id": result["subscription_id"],
            "key_id": settings.razorpay_key_id,
            "user_email": user.email_id,
            "user_name": user.name or user.email_id,
            "plan_name": plan.name,
        },
    )


@router.post("/razorpay-create-plans")
async def create_razorpay_plans_manual(
    session: AsyncSession = Depends(get_db_session),
):
    """One-time endpoint to manually create Razorpay live plans. Remove after use."""
    import asyncio
    from src.razorpayservice.razorpay_client import is_razorpay_enabled, get_razorpay_client
    from src.razorpayservice.razorpay_service import create_razorpay_plan
    from src.settings import get_settings

    import os
    settings = get_settings()
    key_id = settings.razorpay_key_id or "(not set)"
    # Show first 12 chars of key to verify it's the right one, mask the rest
    key_preview = key_id[:12] + "..." if len(key_id) > 12 else key_id

    # Dump ALL ASAM_ env var NAMES to debug loading issues
    raw_env = {}
    for k, v in os.environ.items():
        if "RAZORPAY" in k.upper():
            raw_env[k] = v[:12] + "..." if len(v) > 12 else "(empty)" if not v else v
    # Also list all ASAM_ var names (no values) to spot any naming issue
    all_asam_keys = sorted([k for k in os.environ.keys() if k.startswith("ASAM")])

    if not is_razorpay_enabled():
        return {
            "error": "Razorpay not configured",
            "key_id_preview": key_preview,
            "key_id_type": type(settings.razorpay_key_id).__name__,
            "key_id_value_repr": repr(settings.razorpay_key_id)[:30] if settings.razorpay_key_id else "None",
            "key_secret_set": bool(settings.razorpay_key_secret),
            "raw_env_vars": raw_env,
            "all_asam_var_names": all_asam_keys,
            "hint": "Check ASAM_RAZORPAY_KEY_ID and ASAM_RAZORPAY_KEY_SECRET in App Runner env vars"
        }

    # Test basic connectivity first
    try:
        client = get_razorpay_client()
        test_result = "client created OK"
    except Exception as e:
        return {"error": f"Failed to create Razorpay client: {str(e)}", "key_id_preview": key_preview}

    result = await session.execute(select(Plan))
    all_plans = result.scalars().all()
    results = []

    for plan in all_plans:
        if plan.plan_type == PlanType.FREE:
            results.append({"plan": plan.name, "status": "skipped", "reason": "FREE plan"})
            continue
        if plan.razorpay_plan_id:
            results.append({"plan": plan.name, "status": "exists", "razorpay_plan_id": plan.razorpay_plan_id})
            continue

        try:
            rzp_plan_id = await asyncio.to_thread(
                create_razorpay_plan, plan.plan_type, plan.billing_cycle
            )
            plan.razorpay_plan_id = rzp_plan_id
            session.add(plan)
            results.append({"plan": plan.name, "status": "created", "razorpay_plan_id": rzp_plan_id})
        except Exception as e:
            import traceback
            results.append({
                "plan": plan.name,
                "status": "FAILED",
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()[-500:]
            })

    await session.commit()
    return {"key_id_preview": key_preview, "client_test": test_result, "results": results}


@router.post("/razorpay-sync-my-subscription")
async def razorpay_sync_my_subscription(
    razorpay_subscription_id: str | None = Body(None, embed=True),
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Repair endpoint for users whose Razorpay payment went through but whose
    plan is still showing FREE (e.g. because the webhook never fired and
    they paid before the synchronous verify flow shipped).

    If razorpay_subscription_id is provided (e.g. copied from the Razorpay
    payment-success email), we validate it belongs to this user and activate.

    Otherwise we list the user's most recent Razorpay subscriptions (matched
    via notes.user_id) and activate the newest one that is 'active' or
    'authenticated'.
    """
    from src.razorpayservice.razorpay_service import RazorpayService
    from src.razorpayservice.razorpay_client import is_razorpay_enabled, get_razorpay_client

    if not is_razorpay_enabled():
        raise HTTPException(status_code=503, detail="INR payment gateway is not available.")

    svc = RazorpayService()

    # Case A: caller supplied a specific subscription id
    if razorpay_subscription_id:
        try:
            sub_data = await run_in_threadpool(svc.fetch_subscription, razorpay_subscription_id)
        except Exception as exc:
            logger.error(
                "[RAZORPAY] sync: fetch failed for %s: %s",
                razorpay_subscription_id, exc, exc_info=True,
            )
            raise HTTPException(status_code=502, detail="Could not fetch subscription from Razorpay.")

        notes_user_id = (sub_data.get("notes") or {}).get("user_id")
        if not notes_user_id or str(notes_user_id) != str(current_user.id):
            raise HTTPException(
                status_code=403,
                detail="This subscription does not belong to your account.",
            )

        status = await svc.activate_subscription_from_payment(
            session=session,
            user_id=str(current_user.id),
            razorpay_subscription_id=razorpay_subscription_id,
            subscription_data=sub_data,
        )
        if status != "activated":
            raise HTTPException(
                status_code=409,
                detail=f"Could not activate subscription (reason: {status}).",
            )
        return SuccessResponse(
            message="Subscription activated",
            data={"subscription_id": razorpay_subscription_id},
        )

    # Case B: no id given — search Razorpay for the user's subscriptions.
    try:
        client = get_razorpay_client()
        # Razorpay API: list most recent subscriptions. We then filter by notes.user_id.
        listing = await run_in_threadpool(lambda: client.subscription.all({"count": 50}))
    except Exception as exc:
        logger.error("[RAZORPAY] sync: list failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Could not list subscriptions from Razorpay.")

    items = listing.get("items", []) if isinstance(listing, dict) else []
    user_id_str = str(current_user.id)

    # Keep only this user's subscriptions, newest first.
    candidates = [
        s for s in items
        if ((s.get("notes") or {}).get("user_id") == user_id_str)
    ]
    candidates.sort(key=lambda s: s.get("created_at", 0), reverse=True)

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=(
                "No Razorpay subscription found for this account. "
                "If you just paid, please forward me the subscription id from the payment email."
            ),
        )

    # Prefer an active/authenticated one.
    active_candidates = [
        s for s in candidates
        if (s.get("status") or "").lower() in ("active", "authenticated")
    ]
    chosen = active_candidates[0] if active_candidates else candidates[0]

    sub_id = chosen.get("id")
    status = await svc.activate_subscription_from_payment(
        session=session,
        user_id=user_id_str,
        razorpay_subscription_id=sub_id,
        subscription_data=chosen,
    )
    if status != "activated":
        raise HTTPException(
            status_code=409,
            detail=f"Subscription found ({sub_id}) but activation returned '{status}'.",
        )

    return SuccessResponse(
        message="Subscription activated",
        data={"subscription_id": sub_id, "plan_id": chosen.get("plan_id")},
    )


@router.post("/razorpay-verify-payment")
async def razorpay_verify_payment(
    payload: dict = Body(...),
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Called by the frontend immediately after the Razorpay Checkout JS
    success handler fires. We:
      1. Verify the signature (proves the payment really came from Razorpay).
      2. Fetch the subscription from Razorpay API to read the authoritative
         plan_id / status / period dates.
      3. Create or update the Subscription row and set user.plan_type.

    Making activation synchronous here means the UI can refresh the user's
    plan right away, without waiting for the subscription.activated webhook.
    The webhook remains as a backup for cancellations, renewals, and any
    case where the browser closes before this endpoint is hit.

    Expected body:
        {
          "razorpay_payment_id": "pay_xxx",
          "razorpay_subscription_id": "sub_xxx",
          "razorpay_signature": "<hex>"
        }
    """
    from src.razorpayservice.razorpay_service import RazorpayService
    from src.razorpayservice.razorpay_client import is_razorpay_enabled

    if not is_razorpay_enabled():
        raise HTTPException(status_code=503, detail="INR payment gateway is not available.")

    payment_id      = payload.get("razorpay_payment_id")
    subscription_id = payload.get("razorpay_subscription_id")
    signature       = payload.get("razorpay_signature")

    if not payment_id or not subscription_id or not signature:
        raise HTTPException(
            status_code=400,
            detail="razorpay_payment_id, razorpay_subscription_id and razorpay_signature are required.",
        )

    svc = RazorpayService()

    # 1. Verify signature
    if not svc.verify_payment_signature(payment_id, subscription_id, signature):
        logger.warning(
            "[RAZORPAY] verify-payment: signature mismatch for sub=%s user=%s",
            subscription_id, current_user.id,
        )
        raise HTTPException(status_code=400, detail="Payment signature verification failed.")

    # 2. Fetch the subscription from Razorpay to read plan_id + status
    try:
        sub_data = await run_in_threadpool(svc.fetch_subscription, subscription_id)
    except Exception as exc:
        logger.error(
            "[RAZORPAY] verify-payment: fetch failed for sub=%s: %s",
            subscription_id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail="Could not confirm the subscription with Razorpay. Please refresh in a moment.",
        )

    # 3. Cross-check: the subscription's notes.user_id must match the caller
    notes_user_id = (sub_data.get("notes") or {}).get("user_id")
    if notes_user_id and str(notes_user_id) != str(current_user.id):
        logger.error(
            "[RAZORPAY] verify-payment: user mismatch — sub notes=%s caller=%s",
            notes_user_id, current_user.id,
        )
        raise HTTPException(status_code=403, detail="Subscription does not belong to this user.")

    # 4. Activate in DB
    status = await svc.activate_subscription_from_payment(
        session=session,
        user_id=str(current_user.id),
        razorpay_subscription_id=subscription_id,
        subscription_data=sub_data,
    )

    if status != "activated":
        logger.warning(
            "[RAZORPAY] verify-payment: activation returned '%s' for sub=%s",
            status, subscription_id,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Could not activate subscription (reason: {status}). Please contact support.",
        )

    return SuccessResponse(
        message="Payment verified and subscription activated",
        data={"subscription_id": subscription_id},
    )


@router.post("/razorpay-webhook")
async def razorpay_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Receive and verify Razorpay webhook events.
    Handles: subscription.activated, subscription.charged,
             subscription.cancelled, subscription.completed.
    """
    from src.razorpayservice.razorpay_service import RazorpayService

    body      = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    svc = RazorpayService()

    if not svc.verify_webhook_signature(body, signature):
        logger.warning("[RAZORPAY] Webhook signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except Exception as exc:
        logger.error("[RAZORPAY] Could not parse webhook JSON: %s", exc)
        return {"status": "invalid_json"}

    event         = payload.get("event", "")
    event_payload = payload.get("payload", {})

    logger.info("[RAZORPAY] Webhook received: event=%s", event)

    try:
        status = await svc.handle_event(session, event, event_payload)
        logger.info("[RAZORPAY] Webhook handled: event=%s status=%s", event, status)
        return {"status": status}
    except Exception as exc:
        logger.error("[RAZORPAY] Webhook handler error: %s", exc, exc_info=True)
        return {"status": "handler_error", "error": str(exc)}



