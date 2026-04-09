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
    """
    Idempotent profile creation.
    - If a profile with this auth_user_id already exists, return it (200).
    - If the existing profile is deactivated, return 403.
    - Otherwise, create a new profile + free subscription and return it.
    This endpoint is called from the registration and sign-in flows, which
    may try to create the same profile more than once; this handles the
    duplicate gracefully instead of raising a UNIQUE constraint error.
    """
    try:
        # Idempotency: does this profile already exist?
        existing_stmt = select(UserProfile).where(UserProfile.auth_user_id == data.auth_user_id)
        existing_result = await session.execute(existing_stmt)
        existing_user = existing_result.scalar_one_or_none()

        if existing_user is not None:
            if not existing_user.is_active:
                raise HTTPException(
                    status_code=403,
                    detail="Account deactivated. Please contact support."
                )
            # Profile already exists - return it as-is (idempotent success)
            return existing_user

        # Create new profile
        user = UserProfile(**data.dict())
        session.add(user)
        await session.flush()  # Ensure user.id is generated

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
                current_period_end=None,  # Perpetual free plan
                cancel_at_period_end=False
            )

            session.add(new_sub)

            # Set user plan type
            user.plan_type = PlanType.FREE
            session.add(user)

        await session.commit()
        await session.refresh(user)
        return user
    except HTTPException:
        # Re-raise HTTP exceptions (403 deactivated) so FastAPI handles them
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        # Return a proper 500 so the frontend sees the failure explicitly
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {str(e)}")

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
        raise HTTPException(status_code=404, detail="User not found")
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