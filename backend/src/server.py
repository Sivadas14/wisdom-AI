print("[TRACE] server.py import start")
import logging
import sys

# Initialize logging as early as possible for CloudWatch visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("server")

from tuneapi import tu

import os
import asyncio
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import async_sessionmaker
from fastapi.openapi.utils import get_openapi


from src import db, middlewares
from src.db import dispose_background_engine
from src.services import (
    admin as admin_svc,
    audio as audio_svc,
    auth as auth_svc,
    chat as chat_svc,
    content as content_svc,
    usage as usage_svc,
)
from src.routers.notification_bar import router as notification_bar_router
from src.routers.contemplation import router as contemplation_router


from src.services.plan import router as plan_router
from src.services.plan_feature import router as plan_feature_router
from src.services.plan_price import router as plan_price_router
from src.services.add_on_types import router as add_on_router
from src.routers.subscription import router as plan_subscription_router
from src.services.orders import router as order_router
from src.routers.pollor import router as pollor_router
from src.services.feature import router as feature_router

from src.services.plan_feature_v1 import router as plan_feature_v1_router

from src.login.loginservice import Authorization
from src.dependencies import check_ffmpeg, get_api_token
from src.content.parallel_video import pre_generate_common_images

from src.services.user import router as user_profile_router
from src.services.dashboard import router as dashboard_router
from src.services.ramana_images import router as ramana_images_router
from src.migrations import run_migrations

async def _setup_db(app: FastAPI):
    print("[TRACE] _setup_db() start")
    tu.logger.info("Setting up the database")
    db_engine = db.connect_to_postgres(sync=False)
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    app.state.db_engine = db_engine
    app.state.db_session_factory = session_factory
    print("[TRACE] _setup_db() complete")

async def _setup_optimizations(app: FastAPI):
    """Setup performance optimizations"""
    tu.logger.info("Setting up performance optimizations...")
    
    # Pre-generate common meditation images for faster video generation
    try:
        await pre_generate_common_images()
        tu.logger.info("Performance optimizations setup complete")
    except Exception as e:
        tu.logger.error(f"Failed to setup optimizations: {e}")
        # Don't fail startup if optimizations fail

async def _close_db(app: FastAPI):
    tu.logger.info("Closing the database")
    db_engine = app.state.db_engine
    await db_engine.dispose()
    
    # Also dispose the background engine
    await dispose_background_engine()


# The app itself


@asynccontextmanager
async def lifespan(app: FastAPI):
    deployed_sha = os.getenv("GIT_SHA", "unknown")
    print(f"[TRACE] lifespan() start  GIT_SHA={deployed_sha}")
    logger.info(f"=== DEPLOYED VERSION: {deployed_sha} ===")
    try:
        tu.logger.info("Initializing application lifespan...")
        # Setup
        await _setup_db(app)
        tu.logger.info("Database setup successfully.")

        # Run startup migrations (idempotent — safe on every restart)
        await run_migrations(app.state.db_session_factory)
        tu.logger.info("Startup migrations complete.")
        
        # Start background pre-generation after server is up
        print("[TRACE] scheduling background_image_pregeneration")
        asyncio.create_task(background_image_pregeneration())
        tu.logger.info("Background tasks scheduled.")
        
        print("[TRACE] lifespan() yielding")
        yield
        
        print("[TRACE] lifespan() shutdown start")
        tu.logger.info("Shutting down application lifespan...")
    except Exception as e:
        print(f"[TRACE] CRITICAL: Startup failed during lifespan: {str(e)}")
        tu.logger.error(f"Startup failed: {str(e)}")
        # Re-raise to ensure the process exits on failure
        raise
    finally:
        # Cleanup
        try:
            await _close_db(app)
            tu.logger.info("Database connections closed.")
        except Exception as e:
            tu.logger.error(f"Error during cleanup: {str(e)}")

async def background_image_pregeneration():
    """Pre-generate images in background after server startup"""
    # Wait a bit for server to fully start
    await asyncio.sleep(30)  # Wait 30 seconds after startup
    
    try:
        tu.logger.info("Starting background image pre-generation...")
        await pre_generate_common_images()
    except Exception as e:
        tu.logger.error(f"Background image pre-generation failed: {e}")
        # Don't crash the server if this fails



    

def get_app() -> FastAPI:
    print("[TRACE] get_app() factory called")
    # Run before using
    try:
        check_ffmpeg()
    except Exception as e:
        print(f"[TRACE] WARNING: check_ffmpeg failed: {e}")

    try:
        auth=Authorization()
        print("[TRACE] Authorization initialized")
    except Exception as e:
        print(f"[TRACE] ERROR: Authorization init failed: {e}")
        raise

    # FastAPI
    app = FastAPI(lifespan=lifespan)
    app = middlewares.setup_middlewares(app)
    auth_dependency = [Depends(get_api_token)]
    # Health check endpoints
    @app.get("/health", tags=["health"])
    async def health_check():
        """Unified health check endpoint for App Runner, Render, and LBs"""
        logger.info("[TRACE] Health check endpoint hit")
        return {
            "status": "healthy",
            "timestamp": tu.SimplerTimes.get_now_datetime().isoformat(),
            "service": "Arunachala Samudra API",
            "version": os.getenv("GIT_SHA", "unknown"),
        }

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title="FastAPI application",
            version="1.0.0",
            description="JWT Authentication and Authorization",
            routes=app.routes,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            }
        }
        openapi_schema["security"] = [{"BearerAuth": []}]
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # fmt: off
    # add paths

     
    # Assuming auth = Authorization() is already instantiated

# Public endpoints (no auth dependency)
    app.add_api_route("/api/auth/check-email", auth.check_email_exists, methods=["POST"], tags=["auth"])
    app.add_api_route("/api/auth/register", auth.register_user, methods=["POST"], tags=["auth"])
    app.add_api_route("/api/auth/login", auth.login_user, methods=["POST"], tags=["auth"])
    app.add_api_route("/api/auth/send-otp", auth.send_otp, methods=["POST"], tags=["auth"])
    app.add_api_route("/api/auth/verify-otp", auth.verify_otp, methods=["POST"], tags=["auth"])
    app.add_api_route("/api/auth/google", auth.start_google_oauth, methods=["POST"], tags=["auth"])
    app.add_api_route("/auth/callback",auth.auth_callback,methods=["GET"],tags=["auth"])


    # Protected endpoints (require auth dependency)
    # Replace `auth_dependency` with your actual dependency that validates JWT or session
    app.add_api_route("/api/auth/me", auth.get_current_user, methods=["GET"], tags=["auth"])
    app.add_api_route("/api/auth/logout", auth.logout_user, methods=["POST"], tags=["auth"])
    app.add_api_route("/api/auth/refresh_token", auth.refresh_token, methods=["GET"])
    
    print("[TRACE] Including API routers...")
    app.include_router(user_profile_router)
    app.include_router(plan_router)
    app.include_router(plan_feature_router)
    app.include_router(plan_price_router)
    app.include_router(add_on_router)
    app.include_router(plan_subscription_router)
    app.include_router(order_router)
    app.include_router(dashboard_router)
    app.include_router(ramana_images_router)
    app.include_router(pollor_router)
    app.include_router(notification_bar_router)
    app.include_router(contemplation_router)
    app.include_router(feature_router)
    app.include_router(plan_feature_v1_router)
    print("[TRACE] API routers included.")

    # app.add_api_route("/api/auth/register", auth_svc.new_user, methods=["POST"], tags=["auth"])
    # app.add_api_route("/api/auth/login", auth_svc.login, methods=["POST"], tags=["auth"])
    # app.add_api_route("/api/auth/me", auth_svc.get_current_user, methods=["GET"], tags=["auth"], dependencies=auth_dependency)
    # app.add_api_route("/api/auth/refresh", auth_svc.refresh_jwt, methods=["POST"], tags=["auth"], dependencies=auth_dependency)
    # app.add_api_route("/api/auth/l    ogout", auth_svc.logout, methods=["POST"], tags=["auth"], dependencies=auth_dependency)
    # chat
    app.add_api_route("/api/chat", chat_svc.get_conversations, methods=["GET"], tags=["chat"])
    app.add_api_route("/api/chat", chat_svc.create_conversation, methods=["POST"], tags=["chat"])
    app.add_api_route("/api/chat/{conversation_id}", chat_svc.get_conversation, methods=["GET"], tags=["chat"])
    app.add_api_route("/api/chat/{conversation_id}", chat_svc.chat_completions, methods=["POST"], tags=["chat"])
    app.add_api_route("/api/chat/{conversation_id}", chat_svc.delete_conversation, methods=["DELETE"], tags=["chat"])
    app.add_api_route("/api/chat/{conversation_id}/title", chat_svc.update_conversation_title, methods=["PUT"], tags=["chat"])
    app.add_api_route("/api/chat/{conversation_id}/feedback", chat_svc.submit_conversation_feedback, methods=["POST"], tags=["chat"])
    app.add_api_route("/api/chat/{conversation_id}/mark-as-deleted", chat_svc.mark_conversation_as_deleted, methods=["DELETE"], tags=["chat"],status_code=204)

    # content
    app.add_api_route("/api/content", content_svc.create_content, methods=["POST"], tags=["content"])
    app.add_api_route("/api/content/images", content_svc.get_image_content, methods=["GET"], tags=["content"])
    app.add_api_route("/api/content/media", content_svc.get_media_content, methods=["GET"], tags=["content"])
    app.add_api_route("/api/content/conversation/{conversation_id}", content_svc.get_conversation_content, methods=["GET"], tags=["content"])
    app.add_api_route("/api/content/{content_id}", content_svc.get_content, methods=["GET"], tags=["content"])

    # usage tracking
    app.add_api_route("/api/usage", usage_svc.get_usage, methods=["GET"], tags=["usage"])


    # # audio
    # app.add_api_route("/api/speech/transcribe", audio_svc.transcribe_audio, methods=["POST"], tags=["audio"], dependencies=auth_dependency)
    # app.add_api_route("/api/tts/generate", audio_svc.generate_speech, methods=["POST"], tags=["audio"], dependencies=auth_dependency)

    # admin
    # app.add_api_route("/api/admin/users", admin_svc.list_users, methods=["GET"], tags=["admin"], dependencies=auth_dependency)
    # app.add_api_route("/api/admin/users/{user_id}", admin_svc.delete_user, methods=["DELETE"], tags=["admin"], dependencies=auth_dependency)
    # app.add_api_route("/api/admin/content/{content_id}", admin_svc.delete_content, methods=["DELETE"], tags=["admin"], dependencies=auth_dependency)
    # app.add_api_route("/api/admin/feedback", admin_svc.get_feedback, methods=["GET"], tags=["admin"], dependencies=auth_dependency)
    # app.add_api_route("/api/admin/source-data/list", admin_svc.list_source_data, methods=["GET"], tags=["admin"], dependencies=auth_dependency)
    # # fmt: on

    #admin without confiugration
    app.add_api_route("/api/admin/users", admin_svc.list_users, methods=["GET"], tags=["admin"])
    app.add_api_route("/api/admin/users/{user_id}", admin_svc.get_user_admin_details, methods=["GET"], tags=["admin"])
    app.add_api_route("/api/admin/users/{user_id}", admin_svc.delete_user, methods=["DELETE"], tags=["admin"])
    app.add_api_route("/api/admin/users/{user_id}/toggle-active", admin_svc.toggle_user_active, methods=["PATCH"], tags=["admin"])
    app.add_api_route("/api/admin/content/{content_id}", admin_svc.delete_content, methods=["DELETE"], tags=["admin"])
    app.add_api_route("/api/admin/feedback", admin_svc.get_feedback, methods=["GET"], tags=["admin"])
    app.add_api_route("/api/admin/source-data/list", admin_svc.list_source_data, methods=["GET"], tags=["admin"])
    app.add_api_route("/api/admin/source-data/{document_id}", admin_svc.delete_source_document, methods=["DELETE"], tags=["admin"])
    app.add_api_route("/api/admin/upload", admin_svc.upload_source_pdfs, methods=["POST"], tags=["admin"])
    # Unauthenticated bootstrap — promotes a user to ADMIN via shared secret
    app.add_api_route("/api/admin/make-admin", admin_svc.make_admin, methods=["POST"], tags=["admin"])
    # fmt: on

    # Redundant health check removed (consolidated above)

    # Catch-all route for SPA (Single Page Application) - must be last
    ui_path = tu.joinp(tu.folder(__file__), "ui")

    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        """Serve the React app and its assets from the root."""
        # 1. Protection for API routes - if it starts with api/ but didn't match a route above, it's a 404
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"error": "Not found"})

        # 2. Try to serve exact file from 'ui' folder (assets, images, etc.)
        # If full_path is empty, target is index.html
        target_file = full_path if full_path else "index.html"
        file_path = os.path.join(ui_path, *target_file.split("/"))

        # If it's a real file (hashed JS/CSS asset), serve it with long cache.
        if os.path.isfile(file_path):
            # Hashed assets (e.g. index-abc123.js) are immutable — cache 1 year.
            # index.html itself must never be cached so browsers always get the
            # latest bundle references after a deploy.
            if target_file == "index.html":
                return FileResponse(
                    file_path,
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
                )
            return FileResponse(
                file_path,
                headers={"Cache-Control": "public, max-age=31536000, immutable"},
            )

        # 3. Fallback to index.html for SPA routing (e.g., /signin, /chat, /admin)
        index_file = os.path.join(ui_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(
                index_file,
                headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
            )

        return JSONResponse(status_code=404, content={"error": "Frontend not found"})

    print("[TRACE] API routers included. get_app() returning app.")
    return app


def start_server():
    """Manual server start for debugging/local use"""
    import uvicorn
    app = get_app()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))


if __name__ == "__main__":
    start_server()
