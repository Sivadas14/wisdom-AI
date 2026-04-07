from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, timedelta
from datetime import datetime, timedelta, timezone

from datetime import datetime
from uuid import uuid4

from src.db import (
    get_db_session,
    get_db_session_fa,
    UserProfile,
    Plan,
    PlanType,
    Subscription,
    SubscriptionStatus
)
from src.wire import UserProfileIn
from src.dependencies import get_current_user

router = APIRouter(prefix="/api/profiles", tags=["User Profiles"])
@router.post("/")
async def create_user_profile(data: UserProfileIn, session: AsyncSession = Depends(get_db_session)):
    try:
        user = UserProfile(**data.dict())
        session.add(user)
        await session.flush() # Ensure user.id is generated

        # Find Free Plan
        stmt = select(Plan).where(Plan.plan_type == PlanType.FREE)
        result = await session.execute(stmt)
        free_plan = result.scalar_one_or_none()

        if free_plan:
            # Create default free subscription
            now = datetime.now(timezone.utc)
            
            new_sub = Subscription(
                user_id=user.id,
                plan_id=free_plan.id,
                polar_subscription_id=f"free_{uuid4()}",
                status=SubscriptionStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                current_period_start=now,
                current_period_end=None,  # Set to None for perpetual free plan
                cancel_at_period_end=False
            )
            
            session.add(new_sub)
            
            # Set user plan type
            user.plan_type = PlanType.FREE
            session.add(user)

        await session.commit()
        await session.refresh(user)
        return user
    except Exception as e:
        await session.rollback()
        return {"error": str(e)}

# READ ALL
@router.get("/")
async def get_users(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(UserProfile))
    return result.scalars().all()

# READ ONE
@router.get("/{user_id}")
async def get_user(user_id: str, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(UserProfile).where(UserProfile.auth_user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"error": "User not found"}
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated. Please contact support.")
    return user

# UPDATE
@router.put("/{user_id}")
async def update_user(user_id: str, data: UserProfileIn, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(UserProfile).where(UserProfile.auth_user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"error": "User not found"}
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated. Please contact support.")

    for key, value in data.dict().items():
        setattr(user, key, value)

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

# DELETE
@router.delete("/{user_id}")
async def delete_user(user_id: str, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(UserProfile).where(UserProfile.auth_user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"error": "User not found"}

    await session.delete(user)
    await session.commit()
    return {"status": "User deleted"}


# MARK ONBOARDING SEEN
@router.patch("/me/onboarding-seen")
async def mark_onboarding_seen(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
):
    """Mark the onboarding modal as seen for the authenticated user."""
    current_user.onboarding_seen = True
    session.add(current_user)
    await session.commit()
    return {"onboarding_seen": True}