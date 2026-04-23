"""
Mobile API v1 - Authentication and core endpoints for iOS/Android apps.
"""
import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from src.settings import get_settings, get_supabase_client

router = APIRouter(prefix="/api/v1", tags=["Mobile API"])

class MobileRegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class MobileLoginRequest(BaseModel):
    email: str
    password: str

class MobileRefreshRequest(BaseModel):
    refresh_token: str

class MobileAppleAuthRequest(BaseModel):
    identity_token: str
    nonce: str
    full_name: Optional[str] = None

class MobileGoogleAuthRequest(BaseModel):
    id_token: str

def _get_supabase():
    settings = get_settings()
    return get_supabase_client(settings)

def _build_auth_response(supabase_user, session, name_override: str = "") -> dict:
    name = name_override
    if not name and supabase_user.user_metadata:
        name = supabase_user.user_metadata.get("name", "")
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": 3600,
        "user": {
            "id": str(supabase_user.id),
            "email": supabase_user.email or "",
            "name": name,
            "avatar": None
        }
    }

@router.post("/auth/register")
def mobile_register(request: MobileRegisterRequest):
    supabase = _get_supabase()
    try:
        result = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {"data": {"name": request.name}}
        })
        if not result.user:
            raise HTTPException(status_code=400, detail="Registration failed. Please try again.")
        session = result.session
        if not session:
            try:
                login_result = supabase.auth.sign_in_with_password({
                    "email": request.email,
                    "password": request.password
                })
                session = login_result.session
            except Exception:
                pass
        if not session:
            raise HTTPException(status_code=400, detail="Account created. Please verify your email then sign in.")
        return _build_auth_response(result.user, session, name_override=request.name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/auth/login")
def mobile_login(request: MobileLoginRequest):
    supabase = _get_supabase()
    try:
        result = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        if not result.user or not result.session:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        return _build_auth_response(result.user, result.session)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/auth/refresh")
def mobile_refresh(request: MobileRefreshRequest):
    settings = get_settings()
    try:
        resp = requests.post(
            f"{settings.supabase_url}/auth/v1/token?grant_type=refresh_token",
            json={"refresh_token": request.refresh_token},
            headers={"apikey": settings.supabase_key},
            timeout=10
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
        data = resp.json()
        user = data.get("user", {})
        meta = user.get("user_metadata", {})
        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_in": data.get("expires_in", 3600),
            "user": {"id": user.get("id", ""), "email": user.get("email", ""), "name": meta.get("name", ""), "avatar": None}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/auth/apple")
def mobile_apple_auth(request: MobileAppleAuthRequest):
    supabase = _get_supabase()
    try:
        result = supabase.auth.sign_in_with_id_token({"provider": "apple", "token": request.identity_token, "nonce": request.nonce})
        if not result.user or not result.session:
            raise HTTPException(status_code=401, detail="Apple Sign In failed.")
        return _build_auth_response(result.user, result.session, name_override=request.full_name or "")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/auth/google")
def mobile_google_auth(request: MobileGoogleAuthRequest):
    supabase = _get_supabase()
    try:
        result = supabase.auth.sign_in_with_id_token({"provider": "google", "token": request.id_token})
        if not result.user or not result.session:
            raise HTTPException(status_code=401, detail="Google Sign In failed.")
        return _build_auth_response(result.user, result.session)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/auth/me")
async def mobile_get_me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    email = getattr(user, "email_id", None) or getattr(user, "email", "")
    name = getattr(user, "name", "") or ""
    return {"id": str(user.id), "email": email, "name": name, "avatar": None}

@router.get("/teachings")
async def mobile_teachings(request: Request, page: int = 1, topic_id: Optional[str] = None, search: Optional[str] = None):
    return {"teachings": [], "total": 0, "page": page, "per_page": 20, "has_more": False}

@router.post("/devices/register")
async def mobile_register_device(request: Request):
    return {"success": True, "message": "Device registered"}

@router.get("/notifications/preferences")
async def mobile_get_notification_prefs(request: Request):
    return {"daily_wisdom": True, "meditation_reminder": True, "new_teachings": True, "daily_wisdom_time": "08:00", "meditation_reminder_time": "07:00"}

@router.put("/notifications/preferences")
async def mobile_update_notification_prefs(request: Request):
    return {"success": True}

@router.get("/sync/pull")
async def mobile_sync_pull(request: Request, since: Optional[str] = None):
    return {"bookmarks": [], "reading_progress": [], "last_sync": None}

@router.post("/sync/push")
async def mobile_sync_push(request: Request):
    return {"success": True}

@router.get("/ai/sessions")
async def mobile_get_ai_sessions(request: Request):
    return {"sessions": []}

@router.post("/ai/sessions/{session_id}/messages")
async def mobile_send_ai_message(request: Request, session_id: str):
    raise HTTPException(status_code=501, detail="AI chat coming soon.")
