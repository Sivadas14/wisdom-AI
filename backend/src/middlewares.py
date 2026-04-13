import jwt
import time
from collections import defaultdict, deque
from tuneapi import tu
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
import time

from src.settings import get_settings
from src.wire import SuccessResponse, Error
from src.db import (
    UserProfile, 
    UserRole, 
    Conversation, 
    Subscription, 
    SubscriptionStatus, 
    Plan,
    ContentGeneration,
    ContentType,
    UserAddon,
    AddonType
)
from sqlalchemy.orm import selectinload

# Import existing usage calculation functions
from src.services.usage import (
    calculate_chat_usage,
    calculate_image_usage,
    calculate_meditation_duration_usage,
    calculate_remaining
)

# Setup tu.logger


# Constants
settings = get_settings()
# JWT_SECRET = settings.jwt_secret
# JWT_ALGORITHM = settings.jwt_algorithm
rate_limit_store = defaultdict(lambda: deque())


async def chat_limit_middleware(request: Request, call_next):
    """
    Middleware to enforce chat token limits based on user's plan.
    Applies to chat endpoints (conversation message creation).
    
    Checks chat_limit against current token usage.
    """
    tu.logger.info(f"[CHAT_LIMIT] Processing request: {request.method} {request.url.path}")
    
    # Apply to chat/message endpoints - adjust paths as needed
    chat_endpoints = [
        "/api/conversations/",  # When creating messages in conversations
        "/api/chat",
        "/api/messages"
    ]
    
    # Check if this is a chat-related POST request

    is_chat_endpoint = request.method == "POST" and any(
        request.url.path.startswith(endpoint) for endpoint in chat_endpoints
    )
    
    if is_chat_endpoint:
        tu.logger.info(f"[CHAT_LIMIT] Chat endpoint detected: {request.url.path}")
        user: UserProfile | None = getattr(request.state, "user", None)
        
        if not user:
            tu.logger.warning(f"[CHAT_LIMIT] No user found in request state")
            return JSONResponse(
                content=Error(
                    code="UNAUTHORIZED",
                    message="Authentication required"
                ).model_dump(),
                status_code=401,
            )
        
        tu.logger.info(f"[CHAT_LIMIT] Checking limits for user_id={user.id}, plan_type={user.plan_type}")
        
        session = None
        try:
            # Get database session
            session = request.app.state.db_session_factory()
            
            # Get user's active subscription and plan
            query = (
                select(Subscription, Plan)
                .join(Plan, Subscription.plan_id == Plan.id)
                .where(
                    Subscription.user_id == user.id,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
            
            result = await session.execute(query)
            subscription_plan = result.first()
            
            # If no active subscription, get default plan
            if not subscription_plan:
                tu.logger.info(f"[CHAT_LIMIT] No active subscription found, fetching default plan")
                plan_query = select(Plan).where(Plan.plan_type == user.plan_type).limit(1)
                plan_result = await session.execute(plan_query)
                plan = plan_result.scalar_one_or_none()
                
                if not plan:
                    tu.logger.error(f"[CHAT_LIMIT] No plan found for user_id={user.id}")
                    return JSONResponse(
                        content=Error(
                            code="PLAN_NOT_FOUND",
                            message="No plan found for user. Please contact support.ewew"
                        ).model_dump(),
                        status_code=404,
                    )
            else:
                _, plan = subscription_plan
            
            tu.logger.info(f"[CHAT_LIMIT] User plan: {plan.name}, chat_limit={plan.chat_limit}")
            
            # Get chat limit
            chat_limit = plan.chat_limit
            
            # Check if limit is "Unlimited"
            if isinstance(chat_limit, str) and chat_limit.lower() == "unlimited":
                tu.logger.info(f"[CHAT_LIMIT] Unlimited plan - allowing request")
                return await call_next(request)
            
            # Convert to integer and check
            try:
                chat_limit_int = int(chat_limit)
                
                # If very high number, treat as unlimited
                if chat_limit_int >= 999999:
                    tu.logger.info(f"[CHAT_LIMIT] Very high limit ({chat_limit_int}) - treating as unlimited")
                    return await call_next(request)
                
                # Calculate current token usage
                tokens_used = await calculate_chat_usage(user.id, session)
                tu.logger.info(f"[CHAT_LIMIT] Token usage: {tokens_used}/{chat_limit_int}")
                
                # Check if user has reached their limit
                if tokens_used >= chat_limit_int:
                    remaining = chat_limit_int - tokens_used
                    tu.logger.warning(f"[CHAT_LIMIT] Limit reached for user_id={user.id}: {tokens_used}/{chat_limit_int}")
                    
                    return JSONResponse(
                        content=Error(
                            code="CHAT_TOKEN_LIMIT_REACHED",
                            message=f"You have reached your chat token limit of {chat_limit_int:,} for your {plan.name} plan.",
                            details={
                                "plan_name": plan.name,
                                "plan_type": plan.plan_type.value,
                                "limit": chat_limit_int,
                                "used": tokens_used,
                                "remaining": remaining,
                                "upgrade_required": True,
                                "suggestion": "Upgrade your plan to get more chat tokens or wait for your limit to reset."
                            }
                        ).model_dump(),
                        status_code=403,
                    )
                
                tu.logger.info(f"[CHAT_LIMIT] Limit check passed - proceeding with request")
                    
            except (ValueError, TypeError) as e:
                tu.logger.error(f"[CHAT_LIMIT] Invalid limit format: {chat_limit}, error: {str(e)}")
                # Invalid limit format, allow request to proceed
                pass
            
        except Exception as e:
            tu.logger.exception(f"[CHAT_LIMIT] Error in chat_limit_middleware: {str(e)}")
            
            # Allow request to proceed on error
            return JSONResponse(
                content=Error(
                    code="INTERNAL_ERROR",
                    message="Failed to check chat token limits"
                ).model_dump(),
                status_code=500,
            )
        finally:
            if session:
                await session.close()
    else:
        tu.logger.debug(f"[CHAT_LIMIT] Not a chat endpoint - skipping")
    
    # Continue with the request
    response = await call_next(request)
    return response


async def content_generation_limit_middleware(request: Request, call_next):
    """
    Middleware to enforce content generation limits based on user's plan.
    Applies to POST /api/meditation/create endpoint.
    
    Checks:
    - IMAGE mode: Validates against card_limit
    - AUDIO/VIDEO mode: Validates against max_meditation_duration
    - Plan feature flags: is_audio and is_video
    """
    tu.logger.info(f"[CONTENT_GEN] Processing request: {request.method} {request.url.path}")
    
    # Only apply to content generation endpoint
    if request.method == "POST" and request.url.path == "/api/content":
        tu.logger.info(f"[CONTENT_GEN] Content generation endpoint detected")
        user: UserProfile | None = getattr(request.state, "user", None)
        
        if not user:
            tu.logger.warning(f"[CONTENT_GEN] No user found in request state")
            return JSONResponse(
                content=Error(
                    code="UNAUTHORIZED",
                    message="Authentication required"
                ).model_dump(),
                status_code=401,
            )
        
        tu.logger.info(f"[CONTENT_GEN] Checking limits for user_id={user.id}")
        
        session = None
        try:
            # Get database session
            session = request.app.state.db_session_factory()
            
            # Parse request body to get mode
            body = await request.body()
            import json
            try:
                request_data = json.loads(body)
                mode = request_data.get("mode", "").lower()
                tu.logger.info(f"[CONTENT_GEN] Content mode: {mode}")
            except Exception as e:
                tu.logger.error(f"[CONTENT_GEN] Failed to parse request body: {str(e)}")
                # If we can't parse body, let the endpoint handle it
                return await call_next(request)
            
            # Restore body for the actual endpoint to read
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive
            
            # Get user's active subscription and plan
            query = (
                select(Subscription, Plan)
                .join(Plan, Subscription.plan_id == Plan.id)
                .where(
                    Subscription.user_id == user.id,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
            
            result = await session.execute(query)
            subscription_plan = result.first()
            
            # If no active subscription, get default plan
            if not subscription_plan:
                tu.logger.info(f"[CONTENT_GEN] No active subscription found, fetching default plan")
                plan_query = select(Plan).where(Plan.plan_type == user.plan_type).limit(1)
                plan_result = await session.execute(plan_query)
                plan = plan_result.scalar_one_or_none()
                
                if not plan:
                    tu.logger.error(f"[CONTENT_GEN] No plan found for user_id={user.id}")
                    return JSONResponse(
                        content=Error(
                            code="PLAN_NOT_FOUND",
                            message="No plan found for user. Please contact support.eeeq"
                        ).model_dump(),
                        status_code=404,
                    )
            else:
                _, plan = subscription_plan
            
            tu.logger.info(f"[CONTENT_GEN] User plan: {plan.name}, card_limit={plan.card_limit}, "
                       f"is_audio={plan.is_audio}, is_video={plan.is_video}, "
                       f"max_duration={plan.max_meditation_duration}")
            
            # Fetch active addons to increase limits
            # NOTE: We fetch valid addons to see if they bump the limit
            addon_stmt = (
                select(UserAddon)
                .join(AddonType)
                .where(
                    UserAddon.user_id == user.id,
                    UserAddon.status == "active"
                )
                .options(selectinload(UserAddon.addon))
            )
            addon_res = await session.execute(addon_stmt)
            addons = addon_res.scalars().all()
            
            addon_cards_sum = 0
            addon_minutes_sum = 0
            for ua in addons:
                u_type = ua.addon.unit_type
                if hasattr(u_type, "value"):
                     u_type = u_type.value
                
                if u_type == "CARDS":
                    addon_cards_sum += ua.limit_value
                elif u_type == "MINUTES":
                    addon_minutes_sum += ua.limit_value
            
            tu.logger.info(f"[CONTENT_GEN] Addon limits: cards={addon_cards_sum}, minutes={addon_minutes_sum}")


            # Validate based on content mode
            if mode == "image":
                tu.logger.info(f"[CONTENT_GEN] Validating IMAGE generation")
                # Check if plan allows images OR if user has addon cards
                base_card_limit = plan.card_limit if plan.card_limit else 0
                
                # If plan allows 0, but we have addons, effective limit is addon_cards_sum
                effective_card_limit = base_card_limit + addon_cards_sum
                
                if effective_card_limit == 0:
                    tu.logger.warning(f"[CONTENT_GEN] Image generation not available for user_id={user.id}")
                    return JSONResponse(
                        content=Error(
                            code="FEATURE_NOT_AVAILABLE",
                            message=f"Image generation is not available in your {plan.name} plan and no active addons found.",
                            details={
                                "plan_name": plan.name,
                                "plan_type": plan.plan_type.value,
                                "feature": "image_generation",
                                "upgrade_required": True,
                                "suggestion": "Upgrade your plan or purchase an addon to generate meditation cards."
                            }
                        ).model_dump(),
                        status_code=403,
                    )
                
                # Check if user has reached image limit
                # If plan allows unlimited, effective_card_limit might technically be just addon sum? 
                # No, if plan is unlimited (very high number check), we pass.
                
                if base_card_limit < 999999:  # Not unlimited by plan
                    image_used = await calculate_image_usage(user.id, session)
                    tu.logger.info(f"[CONTENT_GEN] Image usage: {image_used}/{effective_card_limit}")
                    
                    if image_used >= effective_card_limit:
                        remaining = effective_card_limit - image_used
                        tu.logger.warning(f"[CONTENT_GEN] Image limit reached for user_id={user.id}")
                        
                        return JSONResponse(
                            content=Error(
                                code="IMAGE_LIMIT_REACHED",
                                message=f"You have reached your total meditation card limit of {effective_card_limit}.",
                                details={
                                    "plan_name": plan.name,
                                    "plan_type": plan.plan_type.value,
                                    "limit": effective_card_limit,
                                    "used": image_used,
                                    "remaining": remaining,
                                    "upgrade_required": True,
                                    "suggestion": "Upgrade your plan or purchase an addon to continue."
                                }
                            ).model_dump(),
                            status_code=403,
                        )
                else:
                    tu.logger.info(f"[CONTENT_GEN] Unlimited image generation via Plan")
            
            elif mode == "audio":
                tu.logger.info(f"[CONTENT_GEN] Validating AUDIO generation")
                # Check if plan allows audio
                if not plan.is_audio and addon_minutes_sum == 0:
                    tu.logger.warning(f"[CONTENT_GEN] Audio not available for user_id={user.id}")
                    return JSONResponse(
                        content=Error(
                            code="FEATURE_NOT_AVAILABLE",
                            message=f"Audio meditation is not available in your {plan.name} plan.",
                            details={
                                "plan_name": plan.name,
                                "plan_type": plan.plan_type.value,
                                "feature": "audio_meditation",
                                "upgrade_required": True,
                                "suggestion": "Upgrade your plan or buy an addon to access audio guided meditations."
                            }
                        ).model_dump(),
                        status_code=403,
                    )
                
                # Check meditation duration limit
                base_duration = plan.max_meditation_duration if plan.max_meditation_duration else 0
                effective_duration = base_duration + addon_minutes_sum
                
                if base_duration < 999999:  # Not unlimited by plan
                    duration_used = await calculate_meditation_duration_usage(user.id, session)
                    tu.logger.info(f"[CONTENT_GEN] Audio duration usage: {duration_used}/{effective_duration} seconds")
                    
                    if duration_used >= effective_duration:
                        remaining = effective_duration - duration_used
                        tu.logger.warning(f"[CONTENT_GEN] Audio duration limit reached for user_id={user.id}")
                        
                        return JSONResponse(
                            content=Error(
                                code="MEDITATION_DURATION_LIMIT_REACHED",
                                message=f"You have reached your meditation duration limit of {effective_duration} seconds.",
                                details={
                                    "plan_name": plan.name,
                                    "plan_type":plan.plan_type.value,
                                    "limit": effective_duration,
                                    "used": duration_used,
                                    "remaining": remaining,
                                    "limit_minutes": effective_duration // 60,
                                    "used_minutes": duration_used // 60,
                                    "remaining_minutes": remaining // 60 if remaining > 0 else 0,
                                    "upgrade_required": True,
                                    "suggestion": "Upgrade your plan or buy an addon to get more meditation minutes."
                                }
                            ).model_dump(),
                            status_code=403,
                        )
                else:
                    tu.logger.info(f"[CONTENT_GEN] Unlimited audio duration via Plan")
            
            elif mode == "video":
                tu.logger.info(f"[CONTENT_GEN] Validating VIDEO generation")
                # Check if plan allows video
                if not plan.is_video and addon_minutes_sum == 0:
                    tu.logger.warning(f"[CONTENT_GEN] Video not available for user_id={user.id}")
                    return JSONResponse(
                        content=Error(
                            code="FEATURE_NOT_AVAILABLE",
                            message=f"Video meditation is not available in your {plan.name} plan.",
                            details={
                                "plan_name": plan.name,
                                "plan_type": plan.plan_type.value,
                                "feature": "video_meditation",
                                "upgrade_required": True,
                                "suggestion": "Upgrade your plan or buy an addon to access video guided meditations."
                            }
                        ).model_dump(),
                        status_code=403,
                    )
                
                # Check meditation duration limit
                base_duration = plan.max_meditation_duration if plan.max_meditation_duration else 0
                effective_duration = base_duration + addon_minutes_sum
                
                if base_duration < 999999:  # Not unlimited
                    duration_used = await calculate_meditation_duration_usage(user.id, session)
                    tu.logger.info(f"[CONTENT_GEN] Video duration usage: {duration_used}/{effective_duration} seconds")
                    
                    if duration_used >= effective_duration:
                        remaining = effective_duration - duration_used
                        tu.logger.warning(f"[CONTENT_GEN] Video duration limit reached for user_id={user.id}")
                        
                        return JSONResponse(
                            content=Error(
                                code="MEDITATION_DURATION_LIMIT_REACHED",
                                message=f"You have reached your meditation duration limit of {effective_duration} seconds.",
                                details={
                                    "plan_name": plan.name,
                                    "plan_type": plan.plan_type.value,
                                    "limit": effective_duration,
                                    "used": duration_used,
                                    "remaining": remaining,
                                    "limit_minutes": effective_duration // 60,
                                    "used_minutes": duration_used // 60,
                                    "remaining_minutes": remaining // 60 if remaining > 0 else 0,
                                    "upgrade_required": True,
                                    "suggestion": "Upgrade your plan or buy an addon to get more meditation minutes."
                                }
                            ).model_dump(),
                            status_code=403,
                        )
                else:
                    tu.logger.info(f"[CONTENT_GEN] Unlimited video duration via Plan")
            
            tu.logger.info(f"[CONTENT_GEN] Limit checks passed - proceeding with request")
            
        except Exception as e:
            tu.logger.exception(f"[CONTENT_GEN] Error in content_generation_limit_middleware: {str(e)}")
            
            # Allow request to proceed on error
            return JSONResponse(
                content=Error(
                    code="INTERNAL_ERROR",
                    message="Failed to check content generation limits"
                ).model_dump(),
                status_code=500,
            )
        finally:
            if session:
                await session.close()
    else:
        tu.logger.debug(f"[CONTENT_GEN] Not content generation endpoint - skipping")
    
    # Continue with the request
    response = await call_next(request)
    return response


async def rate_limiting_middleware(request: Request, call_next):
    """
    Rate limiting middleware to prevent abuse.
    """
    client_ip = request.client.host
    tu.logger.info(f"[RATE_LIMIT] Processing request from IP: {client_ip}, path: {request.url.path}")
    
    user_limit = 100
    admin_limit = 1000
    window = 60
    current_time = time.time()

    user_requests = rate_limit_store[client_ip]
    
    # Clean old requests outside the time window
    initial_count = len(user_requests)
    while user_requests and user_requests[0] < current_time - window:
        user_requests.popleft()
    cleaned_count = initial_count - len(user_requests)
    
    if cleaned_count > 0:
        tu.logger.debug(f"[RATE_LIMIT] Cleaned {cleaned_count} old requests for IP: {client_ip}")

    is_admin_endpoint = request.url.path.startswith("/api/admin")
    limit = admin_limit if is_admin_endpoint else user_limit
    current_request_count = len(user_requests)
    
    tu.logger.info(f"[RATE_LIMIT] IP: {client_ip}, requests: {current_request_count}/{limit}, "
                f"admin_endpoint: {is_admin_endpoint}")

    if current_request_count >= limit:
        tu.logger.warning(f"[RATE_LIMIT] Rate limit exceeded for IP: {client_ip}, "
                      f"requests: {current_request_count}/{limit}")
        return JSONResponse(
            content=Error(
                code="RATE_LIMIT_EXCEEDED",
                message=f"Rate limit exceeded. Maximum {limit} requests per minute.",
                details={"retry_after": 60},
            ).model_dump(),
            status_code=429,
        )

    user_requests.append(current_time)
    tu.logger.debug(f"[RATE_LIMIT] Request allowed for IP: {client_ip}")
    
    response = await call_next(request)
    return response


async def jwt_auth_middleware(request: Request, call_next):
    """
    JWT authentication middleware.
    Validates Supabase tokens locally via JWKS and populates request.state.user.
    """
    tu.logger.info(f"[JWT_AUTH] Processing request: {request.method} {request.url.path}")
    public_paths = [
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/verify-otp",
        "/api/profiles/",
        "/api/plans/",
        "/api/plan-prices/",
        "/api/plan-features/",
        "/docs",
        "/openapi.json",
        "/api/webhooks/",
        "/api/pollor/",
        "/api/subscriptions/webhook",
        "/api/notification-bar/",
        "/health",
    ]

    if any(request.url.path.startswith(path) for path in public_paths):
        tu.logger.info(f"[JWT_AUTH] Public path - skipping authentication")
        return await call_next(request)

    if request.method == "OPTIONS":
        tu.logger.info(f"[JWT_AUTH] OPTIONS request - skipping authentication")
        return await call_next(request)

    if not request.url.path.startswith("/api/"):
        tu.logger.debug(f"[JWT_AUTH] Non-API path - skipping authentication")
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        tu.logger.warning(f"[JWT_AUTH] Missing or invalid authorization header")
        return JSONResponse(
            content=Error(
                code="UNAUTHORIZED",
                message="Missing or invalid authorization header",
            ).model_dump(),
            status_code=401,
        )

    token = auth_header.split(" ")[1]
    
    session = None
    try:
        # Verify with Supabase JWKS (Local)
        from src.services.auth_utils import verify_supabase_jwt
        
        payload = verify_supabase_jwt(token)
        auth_user_id = payload.get("sub")
        
        if not auth_user_id:
             raise Exception("Token missing 'sub' claim")

        tu.logger.debug(f"[JWT_AUTH] Supabase token verified locally. User ID: {auth_user_id}")

        # Fetch local profile
        session = request.app.state.db_session_factory()
        query = select(UserProfile).where(UserProfile.auth_user_id == auth_user_id)
        result = await session.execute(query)
        user: UserProfile | None = result.scalar_one_or_none()
        
        if user:
            request.state.user = user
            tu.logger.info(f"[JWT_AUTH] User authenticated: id={user.id}, role={user.role}")
        else:
            tu.logger.warning(f"[JWT_AUTH] User verified but not found in local DB: {auth_user_id}")
            return JSONResponse(
                content=Error(
                    code="USER_NOT_FOUND",
                    message="User profile not found",
                ).model_dump(),
                status_code=404,
            )

    except Exception as e:
        tu.logger.warning(f"[JWT_AUTH] Verification failed: {str(e)}")
        return JSONResponse(
            content=Error(code="UNAUTHORIZED", message="Invalid or expired token").model_dump(),
            status_code=401,
        )
    finally:
        if session:
            await session.close()

    response = await call_next(request)
    return response


async def admin_auth_middleware(request: Request, call_next):
    """
    Admin authorization middleware.
    """
    tu.logger.info(f"[ADMIN_AUTH] Processing request: {request.method} {request.url.path}")
    
    if request.method == "OPTIONS":
        tu.logger.info(f"[ADMIN_AUTH] OPTIONS request - skipping authentication")
        return await call_next(request)

    if request.url.path.startswith("/api/admin"):
        tu.logger.info(f"[ADMIN_AUTH] Admin endpoint detected")
        user: UserProfile | None = getattr(request.state, "user", None)
        
        if not user:
            tu.logger.warning(f"[ADMIN_AUTH] No user found in request state")
            return JSONResponse(
                content=Error(code="NOT_FOUND", message="Not Found").model_dump(),
                status_code=404,
            )
        
        if user.role != UserRole.ADMIN:
            tu.logger.warning(f"[ADMIN_AUTH] User {user.id} is not an admin (role: {user.role})")
            return JSONResponse(
                content=Error(code="NOT_FOUND", message="Not Found").model_dump(),
                status_code=404,
            )
        
        tu.logger.info(f"[ADMIN_AUTH] Admin access granted for user_id={user.id}")
    else:
        tu.logger.debug(f"[ADMIN_AUTH] Not an admin endpoint - skipping")

    response = await call_next(request)
    return response



def setup_middlewares(app: FastAPI):
    from src.timing_middleware import request_timing_middleware, measure_middleware_timing
    from functools import partial
    
    # Helper to add timed middleware
    def add_timed_middleware(app, middleware_func, name):
        @app.middleware("http")
        async def timed_wrapper(request: Request, call_next):
            # We need to manually call the actual middleware function
            # The actual middleware function expects (request, call_next)
            # So we wrap it:
            
            async def wrapped_call_next(req):
                return await call_next(req)
                
            start = time.time()
            try:
                # We are wrapping the execution of `middleware_func` itself
                response = await middleware_func(request, call_next)
                return response
            finally:
                end = time.time()
                print(f"[{name}] Execution time: {end - start:.4f}s")
    
    # 1️⃣ CORS (always first, built-in)
    # properly configure cors for credentials
    origins = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://arunachalasamudra.co.in",
        "https://www.arunachalasamudra.co.in",
    ]
    
    # Add configured frontend and backend URLs if they differ
    if settings.frontend_url:
        # Strip trailing slash if present for standard origin format
        clean_frontend = settings.frontend_url.rstrip("/")
        if clean_frontend not in origins:
             origins.append(clean_frontend)

    if settings.backend_url:
        clean_backend = settings.backend_url.rstrip("/")
        if clean_backend not in origins:
            origins.append(clean_backend)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2️⃣ Feature / limit middlewares (run AFTER auth)
    # Note: Middleware added last runs first. 
    # But wait, `app.middleware` decorator order:
    # Top-most decorator runs first on request entry.
    # But here we are calling `app.middleware("http")(func)`.
    # The last one registered wraps the previous ones.
    # So to run feature limits AFTER auth (auth runs first), auth must be registered LAST.
    
    # This means:
    # 1. request_timing (OUTERMOST - Register Last)
    # 2. jwt_auth (Register Second Last)
    # 3. limits (Register First)
    
    # Wait, the previous code had:
    # 1. limits
    # 2. jwt_auth
    # 3. request_timing (Request Timing runs First)
    
    # Let's keep the existing order of registration, just wrap them.
    
    # Feature limits
    add_timed_middleware(app, content_generation_limit_middleware, "ContentGenerationLimit")
    add_timed_middleware(app, conversation_limit_middleware, "ConversationLimit")
    # add_timed_middleware(app, chat_limit_middleware, "ChatLimit")

    # 3️⃣ JWT auth
    add_timed_middleware(app, jwt_auth_middleware, "JWTAuth")

    # 4️⃣ Admin auth (optional)
    # add_timed_middleware(app, admin_auth_middleware, "AdminAuth")

    # 5️⃣ Request Timing (RUNS FIRST - Register Last)
    # matches User desire for "whole request serving timing"
    app.middleware("http")(request_timing_middleware)

    return app

async def conversation_limit_middleware(request: Request, call_next):
    """
    Middleware to enforce conversation creation limits based on user's plan.
    Only applies to POST /api/conversations endpoint.
    """
    tu.logger.info(f"[CONVERSATION] Processing request: {request.method} {request.url.path}")
    
    # Only apply to conversation creation endpoint
    if request.method == "POST" and request.url.path == "/api/chat" and not request.path_params:
        tu.logger.info(f"[CONVERSATION] Conversation creation endpoint detected")
        user: UserProfile | None = getattr(request.state, "user", None)
        
        if not user:
            tu.logger.warning(f"[CONVERSATION] No user found in request state")
            return JSONResponse(
                content=Error(
                    code="UNAUTHORIZED",
                    message="Authentication required"
                ).model_dump(),
                status_code=401,
            )
        
        tu.logger.info(f"[CONVERSATION] Checking limits for user_id={user.id}")
        
        session = None
        try:
            session = request.app.state.db_session_factory()
            
            query = (
                select(Subscription, Plan)
                .join(Plan, Subscription.plan_id == Plan.id)
                .where(
                    Subscription.user_id == user.id,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
            
            result = await session.execute(query)
            subscription_plan = result.first()
            
            if not subscription_plan:
                tu.logger.info(f"[CONVERSATION] No active subscription found, fetching default plan")
                plan_query = select(Plan).where(Plan.plan_type == user.plan_type).limit(1)
                plan_result = await session.execute(plan_query)
                plan = plan_result.scalar_one_or_none()
                
                if not plan:
                    tu.logger.error(f"[CONVERSATION] No plan found for user_id={user.id}")
                    return JSONResponse(
                        content=Error(
                            code="PLAN_NOT_FOUND",
                            message="No plan found for user. Please contact support.fff"
                        ).model_dump(),
                        status_code=404,
                    )
            else:
                _, plan = subscription_plan
            
            conversation_limit = plan.chat_limit if plan.chat_limit else 0
            tu.logger.info(f"[CONVERSATION] User plan: {plan.name}, conversation_limit={conversation_limit}")
            
            if conversation_limit == 'Unlimited':
                tu.logger.info(f"[CONVERSATION] Unlimited conversations - allowing request")
                return await call_next(request)
            
            count_query = (
                select(func.count(Conversation.id))
                .where(
                    Conversation.user_id == user.id,
                    Conversation.deleted_at.is_(None),
                    Conversation.mark_as_deleted == False
                )
            )
            conversation_limit = int(conversation_limit)
            
            count_result = await session.execute(count_query)
            current_count = count_result.scalar_one()
            tu.logger.info(f"[CONVERSATION] Current conversation count: {current_count}/{conversation_limit}")
            
            if current_count >= conversation_limit:
                remaining = conversation_limit - current_count
                tu.logger.warning(f"[CONVERSATION] Limit reached for user_id={user.id}: {current_count}/{conversation_limit}")
                
                return JSONResponse(
                    content=Error(
                        code="CONVERSATION_LIMIT_REACHED",
                        message=f"You have reached your conversation limit of {conversation_limit} for your {plan.name} plan.",
                        details={
                            "plan_name": plan.name,
                            "plan_type": plan.plan_type.value,
                            "limit": conversation_limit,
                            "used": current_count,
                            "remaining": remaining,
                            "upgrade_required": True,
                            "suggestion": "Upgrade your plan to create more conversations or delete existing conversations."
                        }
                    ).model_dump(),
                    status_code=403,
                )
            
            tu.logger.info(f"[CONVERSATION] Limit check passed - proceeding with request")
            
        except Exception as e:
            tu.logger.exception(f"[CONVERSATION] Error in conversation_limit_middleware: {str(e)}")
            return JSONResponse(
                content=Error(
                    code="INTERNAL_ERROR",
                    message="Failed to check conversation limit"
                ).model_dump(),
                status_code=500,
            )
        finally:
            if session:
                await session.close()
    else:
        tu.logger.debug(f"[CONVERSATION] Not conversation creation endpoint - skipping")
    
    response = await call_next(request)
    return response
