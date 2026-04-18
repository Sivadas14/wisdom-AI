"""
Newsletter subscription — Loops integration.

POST /api/newsletter/subscribe  — adds email to Loops
GET  /api/newsletter/test       — diagnostic: tests the Loops API key live
"""

from __future__ import annotations

import logging
import httpx

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from src.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])

# Loops REST API endpoint — requires API key in Authorization header
LOOPS_URL = "https://app.loops.so/api/v1/contacts/create"


class SubscribeRequest(BaseModel):
    email: EmailStr


class SubscribeResponse(BaseModel):
    success: bool
    message: str


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(payload: SubscribeRequest):
    """Add email to Loops via the v1 contacts API."""
    settings = get_settings()
    logger.info("Subscribing %s to Loops", payload.email)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                LOOPS_URL,
                json={"email": str(payload.email), "subscribed": True, "source": "co.in website", "userGroup": "Newsletter"},
                headers={"Authorization": f"ApiKey {settings.loops_api_key}", "Content-Type": "application/json"},
            )

        logger.info("Loops response status=%s body=%s", resp.status_code, resp.text[:300])
        data = resp.json()

        if data.get("success") or data.get("id"):
            return SubscribeResponse(success=True, message="Subscribed successfully.")

        msg = (data.get("message") or "").lower()
        if any(w in msg for w in ("already", "exist", "duplicate", "subscribed")):
            return SubscribeResponse(success=True, message="Already subscribed.")

        logger.error("Loops error %s: %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail=data.get("message", "Unable to subscribe. Please try again."))

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out. Please try again.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
async def test_loops():
    """Diagnostic: calls Loops with a probe email and returns the raw response."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                LOOPS_URL,
                json={"email": "probe@arunachalasamudra.co.in", "subscribed": True, "source": "diagnostic-test"},
                headers={"Authorization": f"ApiKey {settings.loops_api_key}", "Content-Type": "application/json"},
            )
        return {"loops_status": resp.status_code, "loops_body": resp.json(), "key_prefix": settings.loops_api_key[:8] + "..."}
    except Exception as e:
        return {"error": str(e)}
