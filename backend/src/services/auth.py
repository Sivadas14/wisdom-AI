from tuneapi import tu

import hashlib
import secrets
import base64
import datetime
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import jwt

from src import wire as w
from src.db import (
    get_db_session_fa,
    UserProfile,
    UserRole,
    EmailOTP,
    EmailOTPType,
)
from src.dependencies import get_current_user
from src.settings import settings
from src.services.email import (
    generate_otp,
    send_verification_otp,
    send_password_reset_otp,
)


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
# OTP helper — create and store an email OTP
# ============================================================================

async def _create_email_otp(
    session: AsyncSession,
    email: str,
    otp_type: EmailOTPType,
) -> str:
    """Create a new OTP, invalidate old ones, and return the code."""
    # Mark old unused OTPs for this email+type as used (prevent reuse)
    old_query = select(EmailOTP).where(
        and_(
            EmailOTP.email == email,
            EmailOTP.otp_type == otp_type,
            EmailOTP.used == False,
        )
    )
    old_result = await session.execute(old_query)
    for old_otp in old_result.scalars().all():
        old_otp.used = True

    otp_code = generate_otp(6)
    new_otp = EmailOTP(
        email=email,
        otp_code=otp_code,
        otp_type=otp_type,
        expires_at=tu.SimplerTimes.get_now_datetime() + datetime.timedelta(minutes=10),
    )
    session.add(new_otp)
    await session.flush()  # Ensure it's written but don't commit yet
    return otp_code


async def _verify_email_otp(
    session: AsyncSession,
    email: str,
    otp_code: str,
    otp_type: EmailOTPType,
) -> bool:
    """Verify an OTP code. Returns True if valid, False otherwise."""
    now = tu.SimplerTimes.get_now_datetime()
    query = select(EmailOTP).where(
        and_(
            EmailOTP.email == email,
            EmailOTP.otp_type == otp_type,
            EmailOTP.used == False,
            EmailOTP.expires_at > now,
        )
    ).order_by(EmailOTP.created_at.desc()).limit(1)

    result = await session.execute(query)
    otp_record = result.scalar_one_or_none()

    if not otp_record:
        return False

    otp_record.attempts += 1

    if otp_record.attempts > otp_record.max_attempts:
        otp_record.used = True  # Too many attempts
        return False

    if secrets.compare_digest(otp_record.otp_code, otp_code):
        otp_record.used = True  # Mark as consumed
        return True

    return False


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
            phone_verified=False,  # Not verified until email OTP is confirmed
            role=UserRole.USER,
        )

        session.add(new_user_obj)
        await session.flush()  # Get the ID without committing

        # Create and send verification OTP
        otp_code = await _create_email_otp(session, email, EmailOTPType.VERIFICATION)
        email_sent = send_verification_otp(email, otp_code, request.name.strip())

        await session.commit()

        if email_sent:
            return w.SuccessResponse(
                success=True,
                message=f"Account created! A verification code has been sent to {email}. Please check your inbox.",
            )
        else:
            # Account created but email not sent (SMTP not configured)
            return w.SuccessResponse(
                success=True,
                message=f"Account created successfully. You can now sign in with {email}.",
            )

    except Exception as e:
        tu.logger.error(f"Register DB insert failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create account. Database error: {str(e)[:200]}"
        )


async def verify_email(
    request: w.VerifyEmailRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SuccessResponse:
    """POST /api/auth/verify-email — verify email with OTP."""
    email = request.email.strip().lower()
    otp = request.otp.strip()

    if not otp:
        raise HTTPException(status_code=400, detail="Verification code is required")

    # Find user
    user_query = select(UserProfile).where(UserProfile.email == email)
    result = await session.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    if user.phone_verified:  # phone_verified is used as email_verified
        return w.SuccessResponse(success=True, message="Email is already verified")

    # Verify the OTP
    is_valid = await _verify_email_otp(session, email, otp, EmailOTPType.VERIFICATION)

    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code. Please request a new one.")

    user.phone_verified = True  # Mark as verified
    user.last_active_at = tu.SimplerTimes.get_now_datetime()
    await session.commit()

    tu.logger.info(f"Email verified for user: {email}")

    return w.SuccessResponse(
        success=True,
        message="Email verified successfully! You can now sign in.",
    )


async def resend_verification(
    request: w.ResendVerificationRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SuccessResponse:
    """POST /api/auth/resend-verification — resend verification OTP."""
    email = request.email.strip().lower()

    user_query = select(UserProfile).where(UserProfile.email == email)
    result = await session.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal whether the email exists
        return w.SuccessResponse(
            success=True,
            message="If an account exists with this email, a new verification code has been sent.",
        )

    if user.phone_verified:
        return w.SuccessResponse(success=True, message="Email is already verified")

    otp_code = await _create_email_otp(session, email, EmailOTPType.VERIFICATION)
    email_sent = send_verification_otp(email, otp_code, user.name or "")
    await session.commit()

    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again later.")

    return w.SuccessResponse(
        success=True,
        message="A new verification code has been sent to your email.",
    )


async def forgot_password(
    request: w.ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SuccessResponse:
    """POST /api/auth/forgot-password — send password reset OTP."""
    email = request.email.strip().lower()

    user_query = select(UserProfile).where(UserProfile.email == email)
    result = await session.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal whether the email exists (security best practice)
        return w.SuccessResponse(
            success=True,
            message="If an account exists with this email, a password reset code has been sent.",
        )

    otp_code = await _create_email_otp(session, email, EmailOTPType.PASSWORD_RESET)
    email_sent = send_password_reset_otp(email, otp_code, user.name or "")
    await session.commit()

    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send password reset email. Please try again later.")

    return w.SuccessResponse(
        success=True,
        message="If an account exists with this email, a password reset code has been sent.",
    )


async def reset_password(
    request: w.ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SuccessResponse:
    """POST /api/auth/reset-password — reset password using OTP."""
    email = request.email.strip().lower()
    otp = request.otp.strip()
    new_password = request.new_password

    if not otp:
        raise HTTPException(status_code=400, detail="Reset code is required")
    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Find user
    user_query = select(UserProfile).where(UserProfile.email == email)
    result = await session.execute(user_query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    # Verify the OTP
    is_valid = await _verify_email_otp(session, email, otp, EmailOTPType.PASSWORD_RESET)

    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code. Please request a new one.")

    # Update password
    user.password_hash = hash_password(new_password)
    user.is_signed_in = False  # Force re-login with new password
    user.last_active_at = tu.SimplerTimes.get_now_datetime()
    await session.commit()

    tu.logger.info(f"Password reset for user: {email}")

    return w.SuccessResponse(
        success=True,
        message="Password reset successfully! You can now sign in with your new password.",
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
