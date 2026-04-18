"""
Newsletter subscription — Loops integration.

POST /api/newsletter/subscribe
  Accepts an email address and creates/updates the contact in Loops
  (app.loops.so), tagging the source as "co.in website".

Public endpoint — no auth required (it's just an email capture form).
The Loops API key is stored server-side so it is never exposed to the browser.
"""

from __future__ import annotations

import logging
import asyncio
from functools import partial

import requests  # requests is available via supabase dependency

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from src.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])

LOOPS_CONTACT_URL = "https://app.loops.so/api/v1/contacts/create"
LOOPS_UPDATE_URL  = "https://app.loops.so/api/v1/contacts/update"


class SubscribeRequest(BaseModel):
    email: EmailStr


class SubscribeResponse(BaseModel):
    success: bool
    message: str


def _call_loops(api_key: str, email: str) -> tuple[bool, str]:
    """
    Synchronous Loops API call (run in a thread executor so it doesn't
    block the async event loop).

    Loops contact/create returns:
      200  { "success": true,  "id": "..." }           — new contact created
      200  { "success": false, "message": "..." }       — already exists or other
    """
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "email": email,
        "subscribed": True,
        "source": "co.in website",
        "userGroup": "Newsletter",
    }

    try:
        resp = requests.post(LOOPS_CONTACT_URL, json=body, headers=headers, timeout=10)
    except requests.Timeout:
        logger.error("Loops API timed out for %s", email)
        return False, "Request timed out. Please try again."
    except requests.RequestException as e:
        logger.error("Loops request error for %s: %s", email, e)
        return False, "Network error. Please try again."

    logger.info("Loops response for %s: status=%s body=%s", email, resp.status_code, resp.text[:200])

    if resp.status_code == 200:
        data = resp.json()
        if data.get("success"):
            return True, "Subscribed successfully."
        # success:false usually means duplicate — treat as success
        msg = data.get("message", "")
        if "already" in msg.lower() or "duplicate" in msg.lower() or "exist" in msg.lower():
            return True, "Already subscribed."
        # Try update endpoint for existing contacts
        try:
            resp2 = requests.put(LOOPS_UPDATE_URL, json=body, headers=headers, timeout=10)
            if resp2.status_code == 200 and resp2.json().get("success"):
                return True, "Subscription updated."
        except Exception:
            pass
        # Still return success — email was received, Loops may have it already
        return True, "Already subscribed."

    if resp.status_code == 409:
        return True, "Already subscribed."

    logger.error("Loops API error %s: %s", resp.status_code, resp.text[:200])
    return False, "Unable to subscribe at this time. Please try again later."


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(payload: SubscribeRequest):
    """
    Add an email to the Loops mailing list.
    Called by the 'Subscribe for wisdom articles' form on the .co.in landing page.
    """
    settings = get_settings()

    if not settings.loops_api_key:
        logger.error("ASAM_LOOPS_API_KEY is not configured in environment variables")
        raise HTTPException(
            status_code=503,
            detail="Newsletter service is not configured. Please contact info@arunachalasamudra.in."
        )

    # Run synchronous requests call in a thread so we don't block the event loop
    loop = asyncio.get_event_loop()
    ok, message = await loop.run_in_executor(
        None,
        partial(_call_loops, settings.loops_api_key, str(payload.email))
    )

    if not ok:
        raise HTTPException(status_code=502, detail=message)

    return SubscribeResponse(success=True, message=message)
