from src.llm_shim import tu
import subprocess
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db import UserProfile, get_db_session_fa
from src.services.auth_utils import verify_supabase_jwt


bearer_auth = HTTPBearer(auto_error=False)


async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(bearer_auth),
    session: AsyncSession = Depends(get_db_session_fa),
) -> UserProfile:
    """
    FastAPI Dependency to get the current authenticated user.
    1. Extracts Bearer Token
    2. Verifies locally with Supabase JWKS
    3. Fetches local UserProfile from DB
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # 1. Verify Token with Supabase JWKS (Local)
        payload = verify_supabase_jwt(token.credentials)
        
        # 2. Get Supabase User ID (sub field in Supabase JWT)
        auth_user_id = payload.get("sub")
        if not auth_user_id:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: missing sub"
            )
        
        # 3. Fetch Local Profile
        query = select(UserProfile).where(UserProfile.auth_user_id == auth_user_id)
        result = await session.execute(query)
        user_profile = result.scalar_one_or_none()

        if not user_profile:
            tu.logger.warning(f"User authenticated but no local profile found: {auth_user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="User profile not found"
            )

        if not user_profile.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account deactivated. Please contact support."
            )

        return user_profile

    except HTTPException:
        raise
    except Exception as e:
        tu.logger.error(f"Authentication dependency failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed"
        )


def get_api_token(jwt: HTTPAuthorizationCredentials = Depends(bearer_auth)):
    """
    Dummy dependency for Swagger UI
    """
    return jwt


def check_ffmpeg():
    """Check if FFmpeg is installed and accessible"""
    tu.logger.info("Checking if FFmpeg is installed")
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        tu.logger.info("FFmpeg is installed!")
        return True
    except FileNotFoundError:
        tu.logger.error("FFmpeg not found. Please install it first.")
        return False
