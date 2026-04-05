from tuneapi import tu

import hashlib
import secrets
import base64
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
import datetime

from src import wire as w
from src.db import (
    get_db_session_fa,
    UserProfile,
    UserRole,
)
from src.dependencies import get_current_user
from src.settings import settings


# ============================================================================
# Password helpers (using Python standard library — no extra dependencies)
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_bytes(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return base64.b64encode(salt + dk).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        decoded = base64.b64decode(hashed.encode("utf-8"))
        salt = decoded[:32]
        stored_dk = decoded[32:]
        new_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        # Constant-time comparison to prevent timing attacks
        return secrets.compare_digest(new_dk, stored_dk)
    except Exception:
        return False


# ============================================================================
# JWT helpers
# ============================================================================

def create_jwt_tokens(user_id: str) -> tuple[str, str]:
    """Create access and refresh tokens for a user."""
    now = tu.SimplerTimes.get_now_datetime()

    # Access token — expires in 1 hour
    access_payload = {
        "user_id": str(user_id),
        "exp": now + datetime.timedelta(hours=1),
        "iat": now,
        "type": "access",
    }
    access_token = jwt.encode(
        access_payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    # Refresh token — expires in 30 days
    refresh_payload = {
        "user_id": str(user_id),
        "exp": now + datetime.timedelta(days=30),
        "iat": now,
        "type": "refresh",
    }
    refresh_token = jwt.encode(
        refresh_payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    return access_token, refresh_token


# ============================================================================
# Auth endpoints
# ============================================================================

async def login(
    request: w.LoginRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.AuthResponse:
    """POST /api/auth/login — email + password login."""
    email = request.email.strip().lower()

    # Look up user by email
    try:
        user_query = select(UserProfile).where(UserProfile.email == email)
        result = await session.execute(user_query)
        user = result.scalar_one_or_none()
    except Exception as e:
        tu.logger.error(f"Login DB query failed (columns may be missing): {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error — the email column may not exist. Run migrations. Detail: {str(e)[:200]}"
        )

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last active timestamp and mark signed in
    user.last_active_at = tu.SimplerTimes.get_now_datetime()
    user.is_signed_in = True
    await session.commit()
    await session.refresh(user)

    # Generate JWT tokens
    user_bm = await user.to_bm()
    access_token, refresh_token = create_jwt_tokens(user_bm.id)

    return w.AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_bm,
    )


async def logout(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SuccessResponse:
    """POST /api/auth/logout — user logout."""
    user_query = select(UserProfile).where(UserProfile.id == current_user.id)
    result = await session.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_signed_in = False
    user.last_active_at = tu.SimplerTimes.get_now_datetime()
    await session.commit()

    tu.logger.info(f"User {user.id} logged out successfully")

    return w.SuccessResponse(
        success=True,
        message="Successfully logged out",
    )


async def new_user(
    request: w.NewUserRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SuccessResponse:
    """POST /api/auth/register — new user registration."""
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if not request.email or not request.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    if not request.password or len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    email = request.email.strip().lower()

    try:
        # Check if email is already registered
        existing_query = select(UserProfile).where(UserProfile.email == email)
        result = await session.execute(existing_query)
        existing_user = result.scalar_one_or_none()
    except Exception as e:
        tu.logger.error(f"Register DB query failed (columns may be missing): {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error — the email column may not exist. Run migrations. Detail: {str(e)[:200]}"
        )

    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    # Create the new user with a hashed password
    try:
        pw_hash = hash_password(request.password)
        new_user_obj = UserProfile(
            email=email,
            password_hash=pw_hash,
            name=request.name.strip(),
            phone_verified=True,  # email accounts are considered verified on registration
            role=UserRole.USER,
        )

        session.add(new_user_obj)
        await session.commit()
    except Exception as e:
        tu.logger.error(f"Register DB insert failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create account. Database error: {str(e)[:200]}"
        )

    tu.logger.info(f"New user registered: {email}")

    return w.SuccessResponse(
        success=True,
        message=f"Account created successfully. You can now sign in with {email}.",
    )


async def get_current_user(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.User:
    """GET /api/auth/me — get current user profile."""
    current_user.last_active_at = tu.SimplerTimes.get_now_datetime()
    await session.commit()
    return await current_user.to_bm()


async def refresh_jwt(
    request: w.RefreshTokenRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.AuthResponse:
    """POST /api/auth/refresh — refresh authentication tokens."""
    try:
        payload = jwt.decode(
            request.refresh_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Invalid token type")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token payload")

    user_query = select(UserProfile).where(UserProfile.id == user_id)
    result = await session.execute(user_query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_signed_in:
        raise HTTPException(status_code=401, detail="User has been logged out")

    user.last_active_at = tu.SimplerTimes.get_now_datetime()
    await session.commit()
    await session.refresh(user)

    access_token, refresh_token = create_jwt_tokens(user.id)

    return w.AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=await user.to_bm(),
    )
