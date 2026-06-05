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
from fastapi import FastAPI, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse, Response, HTMLResponse
from src.content_pages import get_published_page, render_content_page
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
from src.services import guest_content as guest_content_svc
from src.services.ramana_images import get_portrait as ramana_portrait_handler
from src.routers.notification_bar import router as notification_bar_router
from src.routers.contemplation import router as contemplation_router
from src.routers.newsletter import router as newsletter_router


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
from src.routers.mobile_api import router as mobile_api_router
from src.routers.admin_pages import router as admin_pages_router

# === Translation system routers (added 2026-05-01) ===
from src.translation.gateway import router as translation_router
from src.translation.page_resolver import router as translation_page_router

from src.services.dashboard import router as dashboard_router
from src.services.ramana_images import router as ramana_images_router
from src.migrations import run_migrations
from src.services.cleanup import run_daily_storage_cleanup_loop

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


async def _startup_tasks(app: FastAPI):
    """
    Run DB setup and migrations in the background AFTER the server has already
    yielded.  This means App Runner's health check always sees the port open
    immediately — no more silent reversions due to slow DB connections.
    """
    print("[TRACE] _startup_tasks() begin")

    # ── Database setup ──────────────────────────────────────────────────────
    try:
        await _setup_db(app)
        tu.logger.info("Database setup successfully.")
        print("[TRACE] _startup_tasks(): DB ready")
    except Exception as e:
        print(f"[TRACE] WARNING: DB setup failed: {e}")
        tu.logger.error(f"DB setup error (non-fatal): {e}")
        app.state.db_engine = None
        app.state.db_session_factory = None
        return  # Can't run migrations without a DB

    # ── Startup migrations ──────────────────────────────────────────────────
    if getattr(app.state, "db_session_factory", None) is not None:
        try:
            await run_migrations(app.state.db_session_factory)
            tu.logger.info("Startup migrations complete.")
            print("[TRACE] _startup_tasks(): migrations done")
        except Exception as e:
            print(f"[TRACE] WARNING: Migrations failed (non-fatal): {e}")
            tu.logger.error(f"Migration error (non-fatal): {e}")

    print("[TRACE] _startup_tasks() done")


@asynccontextmanager
async def lifespan(app: FastAPI):
    deployed_sha = os.getenv("GIT_SHA", "unknown")
    print(f"[TRACE] lifespan() start  GIT_SHA={deployed_sha}")
    logger.info(f"=== DEPLOYED VERSION: {deployed_sha} ===")

    # Pre-set state to None so request handlers can check gracefully
    app.state.db_engine = None
    app.state.db_session_factory = None

    # ── Yield FIRST — server is immediately ready for health checks ─────────
    # DB setup and migrations run as background tasks so App Runner's health
    # check always succeeds.  Previously, blocking on DB before yield was the
    # root cause of every silent reversion.
    asyncio.create_task(_startup_tasks(app))
    asyncio.create_task(background_image_pregeneration())
    # Storage cleanup — runs once at startup (after 60s delay) then every 24h
    asyncio.create_task(_run_cleanup_loop(app))
    print("[TRACE] lifespan() yielding — server ready (startup runs in background)")
    tu.logger.info("Background startup tasks scheduled. Server accepting requests.")

    yield  # ← App Runner health check fires here and always succeeds

    # ── Shutdown ────────────────────────────────────────────────────────────
    print("[TRACE] lifespan() shutdown start")
    tu.logger.info("Shutting down application lifespan...")
    try:
        if getattr(app.state, "db_engine", None) is not None:
            await _close_db(app)
            tu.logger.info("Database connections closed.")
    except Exception as e:
        tu.logger.error(f"Error during cleanup: {e}")

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


async def _run_cleanup_loop(app: FastAPI):
    """
    Wait for the DB session factory to be ready (set by _startup_tasks),
    then hand off to the daily storage cleanup loop.
    Polls every 5 s for up to 2 min before giving up.
    """
    for _ in range(24):   # 24 × 5s = 2 minutes max wait
        factory = getattr(app.state, "db_session_factory", None)
        if factory is not None:
            break
        await asyncio.sleep(5)
    else:
        tu.logger.warning("[CLEANUP] DB session factory never became available — skipping cleanup loop")
        return

    tu.logger.info("[CLEANUP] DB ready — starting daily storage cleanup loop")
    try:
        await run_daily_storage_cleanup_loop(app.state.db_session_factory)
    except Exception as e:
        tu.logger.error(f"[CLEANUP] Cleanup loop exited unexpectedly: {e}")



    

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
    app.include_router(newsletter_router)
    app.include_router(feature_router)
    app.include_router(plan_feature_v1_router)
    app.include_router(mobile_api_router)
    app.include_router(admin_pages_router)   # /api/admin/pages (admin-gated)
    # === Translation system routers (added 2026-05-01) ===
    app.include_router(translation_router)        # POST /api/translate
    app.include_router(translation_page_router)   # GET  /api/page/{slug}

    print("[TRACE] API routers included.")

    # app.add_api_route("/api/auth/register", auth_svc.new_user, methods=["POST"], tags=["auth"])
    # app.add_api_route("/api/auth/login", auth_svc.login, methods=["POST"], tags=["auth"])
    # app.add_api_route("/api/auth/me", auth_svc.get_current_user, methods=["GET"], tags=["auth"], dependencies=auth_dependency)
    # app.add_api_route("/api/auth/refresh", auth_svc.refresh_jwt, methods=["POST"], tags=["auth"], dependencies=auth_dependency)
    # app.add_api_route("/api/auth/l    ogout", auth_svc.logout, methods=["POST"], tags=["auth"], dependencies=auth_dependency)
    # chat — guest (public, no auth)
    app.add_api_route("/api/chat/guest", chat_svc.guest_chat_completion, methods=["POST"], tags=["chat"])

    # chat — authenticated
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
    # public portrait for landing-page onboarding — no auth
    app.add_api_route("/api/ramana-portrait", ramana_portrait_handler, methods=["GET"], tags=["guest"])
    # guest content — public, no auth — MUST be before {content_id} wildcard
    app.add_api_route("/api/content/guest", guest_content_svc.create_guest_content, methods=["POST"], tags=["guest"])
    app.add_api_route("/api/content/guest/{content_id}", guest_content_svc.get_guest_content, methods=["GET"], tags=["guest"])
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
    app.add_api_route("/api/admin/suggested-topics", admin_svc.list_suggested_topics, methods=["GET"], tags=["admin"])
    app.add_api_route("/api/admin/suggested-topics/{topic_id}", admin_svc.update_suggested_topic, methods=["PATCH"], tags=["admin"])
    # Public: approved dynamic topics for Chat UI
    app.add_api_route("/api/topics/dynamic", admin_svc.get_dynamic_topics, methods=["GET"], tags=["topics"])
    # fmt: on

    # Redundant health check removed (consolidated above)

    # ── SEO: robots.txt ────────────────────────────────────────────────────────
    @app.get("/robots.txt", include_in_schema=False)
    async def robots_txt():
        """robots.txt — allow all crawlers; point to sitemap."""
        content = "\n".join([
            "User-agent: *",
            "Allow: /",
            "",
            "# Disallow internal app routes that should not be indexed",
            "Disallow: /admin/",
            "Disallow: /callback",
            "Disallow: /profile-completion",
            "Disallow: /reset-password",
            "Disallow: /api/",
            "",
            "Sitemap: https://www.arunachalasamudra.com/sitemap.xml",
            "Sitemap: https://www.arunachalasamudra.co.in/sitemap.xml",
        ])
        return Response(content=content, media_type="text/plain")

    # ── SEO: XML Sitemap ───────────────────────────────────────────────────────
    @app.get("/sitemap.xml", include_in_schema=False)
    async def sitemap_xml(request: Request):
        """
        Dynamic XML sitemap served by the backend so Google can discover
        all public pages regardless of SPA client-side routing.

        Add new public routes here as the platform grows.
        """
        from datetime import date
        today = date.today().isoformat()

        # Static pages with their change frequency and priority
        static_pages = [
            ("",               "daily",   "1.0"),   # homepage / AI chat
            ("privacy",        "yearly",  "0.3"),
            ("terms",          "yearly",  "0.3"),
            ("signin",         "monthly", "0.4"),
            ("register",       "monthly", "0.4"),
        ]

        # Published content pages (migrated .in content)
        try:
            from sqlalchemy import text as _text
            _factory = getattr(request.app.state, "db_session_factory", None)
            if _factory is not None:
                async with _factory() as _sess:
                    _rows = (await _sess.execute(_text(
                        "SELECT canonical_path, slug FROM pages WHERE published = TRUE"
                    ))).mappings().all()
                for _r in _rows:
                    _p = (_r["canonical_path"] or f"/{_r['slug']}").lstrip("/")
                    static_pages.append((_p, "weekly", "0.8"))
        except Exception:
            pass

        urls = []
        base = "https://www.arunachalasamudra.com"
        for path, changefreq, priority in static_pages:
            loc = f"{base}/{path}" if path else base
            urls.append(
                f"  <url>\n"
                f"    <loc>{loc}</loc>\n"
                f"    <lastmod>{today}</lastmod>\n"
                f"    <changefreq>{changefreq}</changefreq>\n"
                f"    <priority>{priority}</priority>\n"
                f"  </url>"
            )

        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
            '        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
            '        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9\n'
            '        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">\n'
            + "\n".join(urls) +
            "\n</urlset>"
        )
        return Response(content=xml, media_type="application/xml")

    # ── Catch-all route for SPA (Single Page Application) - must be last ──────
    ui_path = tu.joinp(tu.folder(__file__), "ui")

    # ── Permanent 301 redirects for typos / old URLs ────────────────────────
    # Key   = the wrong path that was published / indexed by Google
    # Value = the correct canonical path users should land on
    REDIRECTS_301: dict[str, str] = {
        # Legacy Framer .in URLs -> new canonical paths (content migration)
        "arunachala-history": "/arunachala",
        "arunachala-myths": "/arunachala/myths",
        "arunachala-puranam": "/arunachala/puranam",
        "arunachala-significance": "/arunachala/significance",
        "best-times-to-visit-tiruvannamalai": "/arunachala/pilgrimage/best-times",
        "big-temple": "/temple/big-temple",
        "big-temple-architecture": "/temple/architecture",
        "blogs": "/articles",
        "books": "/library/ebooks",
        "curated-links": "/library/resources",
        "deepam-festival": "/arunachala/deepam-festival",
        "festival-calendar": "/temple/festival-calendar",
        "festivals": "/temple/festivals",
        "full-moon": "/arunachala/girivalam",
        "girivalam-importance": "/arunachala/girivalam",
        "girivalam-path": "/arunachala/girivalam",
        "girivalam-right-way": "/arunachala/girivalam",
        "how-to-reach-tiruvannamalai": "/arunachala/pilgrimage/how-to-reach",
        "lingams": "/arunachala/lingams",
        "pilgrimage": "/arunachala/pilgrimage",
        "poems": "/arunachala/poems-hymns",
        "prakarams": "/temple/prakarams",
        "raman-maharshi-core-teachings": "/ramana-maharshi/teachings",
        "ramana-library": "/library",
        "ramana-maharshi-biography": "/ramana-maharshi",
        "ramana-maharshi-core-teachings": "/ramana-maharshi/teachings",
        "ramana-maharshi-direct-disciples": "/ramana-maharshi/disciples",
        "temples-sthalams": "/temple/sthalams",
        "wisdom-ai": "/home",
    }

    @app.get("/{full_path:path}")
    async def catch_all(request: Request, full_path: str):
        """Serve the React app and its assets from the root."""
        # 0. Permanent redirects — typos / old URLs that got indexed or shared
        if full_path in REDIRECTS_301:
            return RedirectResponse(url=REDIRECTS_301[full_path], status_code=301)

        # 1. Protection for API routes - if it starts with api/ but didn't match a route above, it's a 404
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"error": "Not found"})

        # ── Server-rendered public content pages (migrated .in content) ──────
        # If a published page exists for this slug, return real SEO HTML so
        # crawlers and AI engines can read it. Everything else is unchanged.
        if full_path and "." not in full_path.split("/")[-1]:
            _page = None
            _factory = getattr(request.app.state, "db_session_factory", None)
            if _factory is not None:
                try:
                    async with _factory() as _sess:
                        _page = await get_published_page(_sess, full_path)
                except Exception:
                    _page = None
            if _page:
                # Auto-translation turned OFF: serve clean English. Approved,
                # human-reviewed translations will be served here once the admin
                # translation-review workflow is in place.
                return HTMLResponse(
                    render_content_page(_page, lang="en"),
                    headers={"Cache-Control": "public, max-age=300"},
                )

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
