"""
Usage Tracking Service

This module provides functionality to track and calculate user usage
based on their subscription plan limits.
"""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import datetime
from uuid import UUID

from src import wire as w
from src.db import (
    get_db_session_fa,
    UserProfile,
    Subscription,
    SubscriptionStatus,
    Plan,
    PlanType,
    Message,
    Conversation,
    ContentGeneration,
    ContentType,
    UserAddon,
    AddonType
)
from sqlalchemy.orm import selectinload
from src.dependencies import get_current_user


async def calculate_conversation_usage(user_id: UUID, session: AsyncSession, since: datetime.datetime | None = None) -> int:
    """
    Calculate conversation count for a user.
    Counts all conversations (excluding soft-deleted ones).
    
    Args:
        user_id: UUID of the user
        session: Database session
        since: Optional start date for usage calculation
        
    Returns:
        Total count of conversations
    """
    query = (
        select(func.count(Conversation.id))
        .where(
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None),  # Exclude soft-deleted conversations
            Conversation.mark_as_deleted == False
        )
    )
    
    if since:
        query = query.where(Conversation.created_at >= since)
    
    result = await session.execute(query)
    conversation_count = result.scalar_one()
    
    return int(conversation_count) if conversation_count else 0



async def calculate_chat_usage(user_id: UUID, session: AsyncSession, since: datetime.datetime | None = None) -> int:
    """
    Calculate chat token usage for a user.
    Sums input_tokens + output_tokens from messages in user's conversations.
    
    Args:
        user_id: UUID of the user
        session: Database session
        since: Optional start date for usage calculation
        
    Returns:
        Total token count (input + output)
    """
    query = (
        select(
            func.coalesce(
                func.sum(Message.input_tokens + Message.output_tokens), 
                0
            )
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
    )
    
    if since:
        query = query.where(Message.created_at >= since)
    
    result = await session.execute(query)
    total_tokens = result.scalar_one()
    
    return int(total_tokens) if total_tokens else 0


async def calculate_image_usage(user_id: UUID, session: AsyncSession, since: datetime.datetime | None = None) -> int:
    """
    Calculate image generation usage for a user.
    Counts all completed IMAGE type content generations.
    
    Args:
        user_id: UUID of the user
        session: Database session
        since: Optional start date for usage calculation
        
    Returns:
        Count of generated images
    """
    query = (
        select(func.count(ContentGeneration.id))
        .where(
            ContentGeneration.user_id == user_id,
            ContentGeneration.content_type == ContentType.IMAGE,
            ContentGeneration.content_path.isnot(None)  # Only count completed generations
        )
    )
    
    if since:
        query = query.where(ContentGeneration.created_at >= since)
    
    result = await session.execute(query)
    image_count = result.scalar_one()
    
    return int(image_count) if image_count else 0


async def calculate_meditation_duration_usage(user_id: UUID, session: AsyncSession, since: datetime.datetime | None = None) -> int:
    """
    Calculate meditation duration usage for a user.
    Sums duration_seconds for all AUDIO and VIDEO content generations.
    
    Args:
        user_id: UUID of the user
        session: Database session
        since: Optional start date for usage calculation
        
    Returns:
        Total duration in seconds
    """
    query = (
        select(func.coalesce(func.sum(ContentGeneration.duration_seconds), 0))
        .where(
            ContentGeneration.user_id == user_id,
            ContentGeneration.content_type.in_([ContentType.AUDIO, ContentType.VIDEO]),
            ContentGeneration.content_path.isnot(None)  # Only count completed generations
        )
    )
    
    if since:
        query = query.where(ContentGeneration.created_at >= since)
    
    result = await session.execute(query)
    before_total_duration = result.scalar_one()
    print("before Duration in Minutes:", before_total_duration)

    total_duration = before_total_duration//60
    print("Total Duration in Minutes:", total_duration)
    return int(total_duration) if total_duration else 0

def calculate_remaining(limit: str | int, used: int) -> str | int:
    """
    Calculate remaining usage based on limit and used amount.
    
    Args:
        limit: Plan limit (can be "Unlimited" or a number)
        used: Amount already used
        
    Returns:
        Remaining amount ("Unlimited" or a number, can be negative if over limit)
    """
    if isinstance(limit, str) and limit.lower() == "unlimited":
        return "Unlimited"
    
    try:
        limit_int = int(limit)
        remaining = limit_int - used
        return remaining
    except (ValueError, TypeError):
        # If limit is not a valid number or "Unlimited", treat as 0
        return -used
async def get_usage(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.UserUsageResponse:
    """
    GET /api/usage - Get user's current usage statistics
    
    Returns comprehensive usage data including:
    - Conversation count usage vs limit
    - Chat token usage vs limit
    - Image generation usage vs limit
    - Meditation duration usage vs limit
    - Plan information and feature flags
    
    Args:
        current_user: Authenticated user from dependency
        session: Database session
        
    Returns:
        UserUsageResponse with all usage statistics
    """
    # Get user's active subscription and plan
    query = (
        select(Subscription, Plan)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(
            Subscription.user_id == current_user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    
    result = await session.execute(query)
    subscription_plan = result.first()
    
    # If no active subscription, get default plan based on user's plan_type
    if not subscription_plan:
        plan_query = select(Plan).where(Plan.plan_type == current_user.plan_type).limit(1)
        plan_result = await session.execute(plan_query)
        plan = plan_result.scalar_one_or_none()
        
        if not plan:
            raise HTTPException(
                status_code=404,
                detail="No plan found for user. Please contact support.eeee"
            )
    else:
        sub, plan = subscription_plan
    
    # Calculate usage
    # RESET LOGIC: 
    # For PAID plans, we only count usage since the start of the current period.
    # For FREE plan, usage is cumulative (since = None).
    usage_since = None
    if plan.plan_type != PlanType.FREE:
        if subscription_plan and sub.current_period_start:
             usage_since = sub.current_period_start
             print(f"DEBUG: Calculating usage since {usage_since} for paid plan {plan.name}")
        else:
             print(f"DEBUG: No subscription start date found for paid plan {plan.name}, using cumulative.")

    conversation_used = await calculate_conversation_usage(current_user.id, session, since=usage_since)
    chat_used = await calculate_chat_usage(current_user.id, session, since=usage_since)
    image_used = await calculate_image_usage(current_user.id, session, since=usage_since)
    meditation_used = await calculate_meditation_duration_usage(current_user.id, session, since=usage_since)
    
    # --- ADDON CALCULATION ---
    
    # Fetch active addons
    addon_stmt = (
        select(UserAddon)
        .join(AddonType)
        .where(
            UserAddon.user_id == current_user.id,
            UserAddon.status == "active"
        )
        .options(selectinload(UserAddon.addon))
    )
    addon_res = await session.execute(addon_stmt)
    addons = addon_res.scalars().all()
    
    # Sum up Addon Limits
    addon_cards_limit = 0
    addon_minutes_limit = 0
    
    for ua in addons:
        # Check unit type safely (assuming AddonType has unit_type enum as string or enum)
        u_type = ua.addon.unit_type
        if hasattr(u_type, "value"):
            u_type = u_type.value # Handle Enum
            
        if u_type == "CARDS":
            addon_cards_limit += ua.limit_value
        elif u_type == "MINUTES":
            addon_minutes_limit += ua.limit_value

    # Plan Limits
    # card_limit >= 9999 is treated as "Unlimited" (used for Seeker/Devotee plans)
    UNLIMITED_THRESHOLD = 9999
    plan_card_limit_raw = plan.card_limit if plan.card_limit is not None else 0
    cards_unlimited = plan_card_limit_raw >= UNLIMITED_THRESHOLD
    plan_card_limit = plan_card_limit_raw  # numeric, used for arithmetic
    plan_meditation_limit = plan.max_meditation_duration if plan.max_meditation_duration is not None else 0

    # Dynamic Usage Calculation (Plan First, then Addon) - REQUESTED BY USER

    # 1. Cards (Images)
    if cards_unlimited:
        plan_cards_used = image_used
        remaining_image_usage = 0
    else:
        plan_cards_used = min(image_used, plan_card_limit)
        remaining_image_usage = max(0, image_used - plan_card_limit)

    # Addon Usage
    addon_cards_used = min(remaining_image_usage, addon_cards_limit)

    # 2. Minutes (Meditation)
    plan_meditation_used = min(meditation_used, plan_meditation_limit)
    remaining_meditation_usage = max(0, meditation_used - plan_meditation_limit)

    # Addon Usage
    addon_minutes_used = min(remaining_meditation_usage, addon_minutes_limit)

    # Build response
    return w.UserUsageResponse(
        plan_name=plan.name,
        plan_type=plan.plan_type.value if hasattr(plan.plan_type, "value") else plan.plan_type,
        conversations=w.UsageLimit(
            limit=plan.chat_limit if plan.chat_limit else 0,
            used=conversation_used,
            remaining=calculate_remaining(
                plan.chat_limit if plan.chat_limit else 0,
                conversation_used
            )
        ),
        chat_tokens=w.UsageLimit(
            limit=plan.chat_limit,
            used=chat_used,
            remaining=calculate_remaining(plan.chat_limit, chat_used)
        ),
        image_cards=w.UsageLimit(
            limit="Unlimited" if cards_unlimited else plan_card_limit,
            used=plan_cards_used,
            remaining="Unlimited" if cards_unlimited else max(0, plan_card_limit - plan_cards_used)
        ),
        meditation_duration=w.UsageLimit(
            limit=plan_meditation_limit,
            used=plan_meditation_used,
            remaining=max(0, plan_meditation_limit - plan_meditation_used)
        ),
        # New Addon Fields
        addon_cards=w.UsageLimit(
            limit=addon_cards_limit,
            used=addon_cards_used,
            remaining=max(0, addon_cards_limit - addon_cards_used)
        ),
        addon_minutes=w.UsageLimit(
            limit=addon_minutes_limit,
            used=addon_minutes_used,
            remaining=max(0, addon_minutes_limit - addon_minutes_used)
        ),
        audio_enabled=plan.is_audio,
        video_enabled=plan.is_video
    )
