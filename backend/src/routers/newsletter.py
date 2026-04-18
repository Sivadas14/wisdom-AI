"""
Newsletter subscription — stores emails in the newsletter_subscribers table.

POST /api/newsletter/subscribe  — saves email to database
GET  /api/newsletter/test       — returns subscriber count (diagnostic)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import NewsletterSubscriber, get_db_session_fa

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])


class SubscribeRequest(BaseModel):
    email: EmailStr


class SubscribeResponse(BaseModel):
    success: bool
    message: str


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(
    payload: SubscribeRequest,
    db: AsyncSession = Depends(get_db_session_fa),
):
    """Save subscriber email to the database."""
    email = str(payload.email).lower().strip()
    logger.info("Newsletter subscribe request: %s", email)

    try:
        subscriber = NewsletterSubscriber(email=email, source="co.in website")
        db.add(subscriber)
        await db.commit()
        logger.info("Saved new subscriber: %s", email)
        return SubscribeResponse(success=True, message="Subscribed successfully.")

    except IntegrityError:
        await db.rollback()
        logger.info("Duplicate subscriber (already exists): %s", email)
        return SubscribeResponse(success=True, message="Already subscribed.")

    except Exception as e:
        await db.rollback()
        logger.error("Error saving subscriber %s: %s", email, e)
        raise HTTPException(status_code=500, detail="Unable to subscribe. Please try again.")


@router.get("/test")
async def test_newsletter(db: AsyncSession = Depends(get_db_session_fa)):
    """Diagnostic: returns total subscriber count."""
    try:
        result = await db.execute(select(func.count()).select_from(NewsletterSubscriber))
        count = result.scalar()
        return {"status": "ok", "total_subscribers": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
