import os
import uuid
import base64
import hashlib
import requests

from fastapi import (
    FastAPI,
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

# Import the functions, not the settings object directly to avoid circular imports
from src.settings import get_settings, get_supabase_client, get_supabase_admin_client, get_supabase_jwt_client

# PKCE utility - fix the import
from src.login.pkce import generate_pkce  # Changed to match the actual function name

# DTOs
from src.login.dto import (
    EmailRequest,
    RegisterRequest,
    LoginRequest,
    VerifyOtpRequest,
    UserInfo,
    UserToken,
)

class Authorization:
    def __init__(self):
        # Don't initialize supabase client in __init__ to avoid early import issues
        self._supabase = None
        self._supabase_admin = None
        self.PKCE_STORE = {}

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_supabase_client(get_settings())
        return self._supabase

    @property
    def supabase_admin(self):
        """Admin client using service role key — required for auth.admin.* operations."""
        if self._supabase_admin is None:
            self._supabase_admin = get_supabase_admin_client(get_settings())
        return self._supabase_admin

    def start_google_oauth(self, settings = Depends(get_settings)):
        code_verifier, code_challenge = generate_pkce()
        state = str(uuid.uuid4())

        self.PKCE_STORE[state] = code_verifier

        oauth_url = (
            f"{settings.supabase_url}/auth/v1/authorize"
            f"?provider=google"
            f"&redirect_to={settings.backend_url}/auth/callback"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&state={state}"
        )

        return {"url": oauth_url}
 
    def auth_callback(self, code: str, state: str, settings = Depends(get_settings)):
        print("\n=== AUTH CALLBACK START ===")
        print(f"Received code: {code[:20]}..." if code else "No code received")
        print(f"Received state: {state}")
        print(f"PKCE_STORE keys: {list(self.PKCE_STORE.keys())}")
        
        if state not in self.PKCE_STORE:
            print(f"ERROR: State '{state}' not found in PKCE_STORE")
            raise HTTPException(status_code=400, detail="Invalid OAuth state")

        code_verifier = self.PKCE_STORE.pop(state)
        print(f"Retrieved code_verifier: {code_verifier[:20]}...")

        # Exchange code → tokens
        token_url = f"{settings.supabase_url}/auth/v1/token?grant_type=pkce"
        print(f"Token exchange URL: {token_url}")
        
        token_res = requests.post(
            token_url,
            json={"auth_code": code, "code_verifier": code_verifier},
            headers={"apikey": settings.supabase_key},
        )
        
        print(f"Token response status: {token_res.status_code}")
        print(f"Token response body: {token_res.text[:200]}...")

        if token_res.status_code != 200:
            print(f"ERROR: OAuth token exchange failed with status {token_res.status_code}")
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")

        tokens = token_res.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        print(f"Access token received: {access_token[:20]}...")
        print(f"Refresh token received: {refresh_token[:20]}...")

        # Redirect to frontend with tokens
        redirect_url = (
            f"{settings.frontend_url}/auth/success"
            f"#access_token={access_token}"
            f"&refresh_token={refresh_token}"
        )
        print(f"Redirecting to: {redirect_url[:100]}...")
        print("=== AUTH CALLBACK END ===\n")

        return RedirectResponse(redirect_url)
    
    async def check_email_exists(self, request: EmailRequest):
        try:
            result = self.supabase_admin.auth.admin.list_users()
            users = result.users if hasattr(result, "users") else []

            email_exists = any(user.email == request.email for user in users)
            return {"exists": email_exists}

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    async def register_user(self, request: RegisterRequest):
        try:
            result = self.supabase.auth.sign_up({
                "email": request.email,
                "password": request.password,
                "options": {
                    "data": {
                        "name": request.name,
                        "phone": request.phone
                    }
                }
            })

            if result.user:
                return {
                    "success": True,
                    "message": "Registration successful",
                    "userId": result.user.id
                }

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed"
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    async def login_user(self, request: LoginRequest):
        try:
            print("\n=== LOGIN USER START ===")
            print(f"Login attempt for email: {request.email}")
            print(f"Password provided: {'Yes' if request.password else 'No'}")
            
            result = self.supabase.auth.sign_in_with_password({
                "email": request.email,
                "password": request.password
            })
            
            print(f"Supabase response received")
            print(f"User object present: {result.user is not None}")
            print(f"Session object present: {result.session is not None}")

            if not result.user or not result.session:
                print("ERROR: Missing user or session in response")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            print(f"User ID: {result.user.id}")
            print(f"User email: {result.user.email}")
            print(f"User metadata: {result.user.user_metadata}")
            print(f"Access token: {result.session.access_token[:20]}...")
            print(f"Refresh token: {result.session.refresh_token[:20]}...")

            # Build our Pydantic response model
            user_info = UserInfo(
                id=result.user.id,
                email=result.user.email,
                name=result.user.user_metadata.get("name") if result.user.user_metadata else "",
                jwt=result.session.access_token,
                refresh=result.session.refresh_token
            )
            
            print(f"UserInfo created successfully")
            print("=== LOGIN USER SUCCESS ===\n")

            return {
                "success": True,
                "user": user_info
            }

        except Exception as e:
            print(f"\n=== LOGIN USER ERROR ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print("=== LOGIN USER ERROR END ===\n")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e) +"""""dkjflkdsjs"""
            )

    async def send_otp(self, request: EmailRequest, session=None):
        try:
            # --- Guard 1: User must already be registered ---
            # We check our own UserProfile table (email_id column) rather than
            # calling admin.list_users() which lists every user and is expensive.
            # The DB session is injected by FastAPI if the route uses Depends.
            # If no session available (legacy call path), fall back to Supabase admin list.
            from src.db import get_db_session_fa
            from sqlalchemy import select as sa_select
            from src import db as db_module

            # Use Supabase admin API to check existence — lightweight single-email filter
            try:
                all_users = self.supabase_admin.auth.admin.list_users()
                users_list = all_users if isinstance(all_users, list) else (all_users.users if hasattr(all_users, "users") else [])
                matched = [u for u in users_list if u.email == request.email]
                if not matched:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No account found with this email. Please register first before signing in with OTP.",
                    )

                # --- Guard 2: Email must be verified ---
                user_obj = matched[0]
                email_confirmed = getattr(user_obj, "email_confirmed_at", None)
                if not email_confirmed:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Your email is not yet verified. Please check your inbox for the confirmation link sent when you registered.",
                    )

            except HTTPException:
                raise
            except Exception as lookup_err:
                # If the admin lookup fails for any reason, log and proceed cautiously
                print(f"Warning: send_otp user lookup failed: {lookup_err}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not verify account status. Please try again.",
                )

            # All guards passed — send OTP without creating new accounts
            self.supabase.auth.sign_in_with_otp({
                "email": request.email,
                "options": {"should_create_user": False}
            })
            return {"success": True, "message": "OTP sent successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    async def verify_otp(self, request: VerifyOtpRequest):
        try:
            result = self.supabase.auth.verify_otp({
                "email": request.email,
                "token": request.otp,
                "type": "email"
            })

            if result.user:
                return {
                    "success": True,
                    "user": result.user.dict(),
                    "session": result.session.dict() if result.session else None
                }

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP"
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    async def google_auth(self):
        result = self.supabase.auth.sign_in_with_oauth({"provider": "google"})
        return {"url": result.url}

    async def logout_user(self, user_token: UserToken):
        try:
            print("START")
            client = get_supabase_jwt_client(user_token.token)
            client.auth.sign_out()
            return {"success": True, "message": "Logged out successfully"}

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    async def get_current_user(self, token: str = Query(...)):
        try:
            client = get_supabase_client()
            
            if client is None:
                raise HTTPException(
                    status_code=401,
                    detail="Failed to create Supabase client with provided token"
                )
            
            result = client.auth.get_user(token)
            print("RESULT")
            print(result)
            
            if not result or not result.user:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token or session expired"
                )
            
            return {"user": result.user.dict()}
          
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error in get_current_user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}"
            )

    async def refresh_token(self, access_token: str = Query(...), refresh_token: str = Query(...)):
        try:
            client = get_supabase_client()
            
            if client is None:
                raise HTTPException(
                    status_code=401,
                    detail="Failed to create Supabase client with provided token"
                )
      
            response = client.auth.set_session(access_token, refresh_token)
            
            return {"user": response.dict()}
          
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error in refresh_token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token refresh failed: {str(e)}"
            )

app = FastAPI()
auth = Authorization()

# Routes
app.post("/auth/check-email")(auth.check_email_exists)
# app.post("/auth/register")(auth.register_user)
# app.post("/auth/login")(auth.login_user)
# app.post("/auth/send-otp")(auth.send_otp)
# app.post("/auth/verify-otp")(auth.verify_otp)
# app.post("/auth/google")(auth.google_auth)
# app.post("/auth/logout")(auth.logout_user)
# app.get("/auth/me")(auth.get_current_user)