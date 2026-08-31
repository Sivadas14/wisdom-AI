import datetime
from typing import List, Optional
from fastapi import BackgroundTasks, Depends, Query, HTTPException, APIRouter
from supabase import Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID
import uuid

from src.llm_shim import tu
from src import wire as w
from src.db import (
    get_db_session_fa,
    UserProfile,
    ContentGeneration,
    ContentType,
    Conversation,
)
from src.dependencies import get_current_user
from src.settings import get_supabase_client, get_supabase_admin_client
from src.services.usage import get_usage
from src.services import credits as C
from src.services import media_access
from src.content.video import generate_video_content
from src.content.audio import generate_audio_content
from src.content.image import generate_image_content

# Create helper function to map DB model to Wire model
def map_to_wire_content(content: ContentGeneration, spb_client: Client) -> w.ContentGeneration:
    # Trust the DB status column (written by background tasks). Fall back to
    # inferring from content_path only if the row somehow has no status set
    # (shouldn't happen — column has a server_default of 'pending').
    status = getattr(content, "status", None) or (
        "complete" if content.content_path else "processing"
    )
    error_message = getattr(content, "error_message", None)
    content_url = None

    if content.content_path and status == "complete":
        try:
             # Generate presigned URL for download (expires in 10 years)
            presigned_response = spb_client.storage.from_(
                "generations"
            ).create_signed_url(
                content.content_path, 315360000  # 10 years expiry
            )
            content_url = presigned_response.get("signedURL")
        except:
             # If URL generation fails, meaningful fallback or just None
             pass

    return w.ContentGeneration(
        id=str(content.id),
        status=status,
        conversation_id=str(content.conversation_id),
        message_id=str(content.message_id),
        content_type=content.content_type.value,
        content_url=content_url,
        created_at=content.created_at,
        transcript=content.transcript,
        error_message=error_message,
    )


# ── Duplicate requests ───────────────────────────────────────────────────────

async def _existing_in_flight(
    session, user_id, request, content_type,
) -> str | None:
    """The id of an identical generation already running, if there is one.

    The ledger's UNIQUE (content_generation_id, kind) stops one generation
    being charged twice, but it cannot stop a double-clicked button, because
    each request mints a fresh generation id and two ids are two legitimate
    generations. The guard has to be here, before the row is created.

    Matching on (user, conversation, message, type) rather than on a
    client-supplied key means it also covers a refresh mid-generation and a
    retried request, and it saves the duplicated compute as well as the
    duplicated charge. The caller is handed the running job to poll.
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
    row = (await session.execute(
        select(ContentGeneration)
        .where(
            ContentGeneration.user_id == user_id,
            ContentGeneration.conversation_id == request.conversation_id,
            ContentGeneration.message_id == request.message_id,
            ContentGeneration.content_type == content_type,
            ContentGeneration.status.in_(("pending", "processing")),
            ContentGeneration.created_at >= cutoff,
        )
        .order_by(ContentGeneration.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    return str(row.id) if row else None


async def _charge_if_needed(session, user, decision, content_id) -> None:
    """Take the credits for a generation, if credits are what is paying.

    Silent when the mode is off, when the seeker is an admin, on a trial or on
    a legacy plan, and when cards are being made. In shadow mode the debit is
    written for real — that is the point of shadow, to prove the ledger against
    live traffic — but nothing was blocked upstream, so a shadow debit can take
    someone to zero without stopping them. That is intended and is why shadow
    is a staging step rather than a production one.
    """
    if decision is None or not decision.charge or decision.cost <= 0:
        return
    try:
        result = await C.debit_for_generation(
            user.id, decision.cost, content_id, session,
            note=f"{decision.cost} credit(s)",
        )
        tu.logger.info(
            f"[CREDITS] debited {result.charged} for generation {content_id}; "
            f"balance now {result.balance}"
        )
    except Exception as e:      # noqa: BLE001
        # Never fail the generation over the ledger. An uncharged generation
        # costs us one meditation; a failed request costs a seeker theirs.
        tu.logger.error(f"[CREDITS] debit failed for {content_id}: {e}")


async def create_content(
    request: w.ContentGenerationRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_admin_client),
    current_user: UserProfile = Depends(get_current_user),
) -> w.ContentGenerationResponse:
    """POST /api/meditation/create - Generate meditation content"""

    # ── Credits ─────────────────────────────────────────────────────────────
    # Runs BEFORE the plan quota below, and in "on" mode replaces it for media.
    #
    #   off    — skipped entirely; the plan quota decides, as it does today.
    #   shadow — the decision is computed and logged, and nothing is blocked.
    #            This is how the wallet is proven against real traffic before
    #            anyone's experience depends on it.
    #   on     — credits decide. Insufficient credits returns 402.
    #
    # 402 deliberately: 403 is what the interceptor reads as a deactivated
    # account, and 429 is what it reads as a subscription paywall. Neither is
    # what "you need one more credit" means.
    media_decision = None
    media_minutes = 0
    if request.mode in ("audio", "video") and C.credits_mode() != "off":
        media_minutes = media_access.parse_minutes(request.length)
        try:
            media_decision = await media_access.decide(
                current_user, media_minutes, session
            )
        except Exception as e:      # noqa: BLE001
            # A wallet failure must not stop someone generating; it falls
            # through to the plan quota, which is the behaviour we had before.
            tu.logger.error(f"[CREDITS] media decision failed, falling through: {e}")
            media_decision = None

        if media_decision is not None:
            tu.logger.info(
                f"[CREDITS] mode={C.credits_mode()} user={current_user.id} "
                f"{request.mode} {media_minutes}min cost={media_decision.cost} "
                f"reason={media_decision.reason} allowed={media_decision.allowed}"
            )
            if C.credits_mode() == "on" and not media_decision.allowed:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "code": "INSUFFICIENT_CREDITS",
                        "message": (
                            f"You need {media_decision.cost} credit"
                            f"{'s' if media_decision.cost != 1 else ''} to create this."
                        ),
                        "required": media_decision.cost,
                        "balance": media_decision.balance,
                    },
                )

    # Backend quota enforcement — check limits before generating any content
    try:
        usage = await get_usage(current_user=current_user, session=session)

        if request.mode == "image":
            # Check contemplation card (image) quota
            cards_remaining = usage.image_cards.remaining
            addon_remaining = getattr(usage.addon_cards, 'remaining', 0) or 0
            if isinstance(cards_remaining, int) and cards_remaining <= 0 and addon_remaining <= 0:
                raise HTTPException(
                    status_code=429,
                    detail="You have reached your contemplation card limit. Please upgrade your plan to generate more."
                )

        elif request.mode in ("audio", "video"):
            # Check meditation (audio/video) quota
            if request.mode == "audio" and not usage.audio_enabled:
                raise HTTPException(
                    status_code=429,
                    detail="Audio meditation is not enabled in your plan. Please upgrade to access this feature."
                )
            if request.mode == "video" and not usage.video_enabled:
                raise HTTPException(
                    status_code=429,
                    detail="Video meditation is not enabled in your plan. Please upgrade to access this feature."
                )
            minutes_remaining = usage.meditation_duration.remaining
            addon_minutes = getattr(usage.addon_minutes, 'remaining', 0) or 0
            if isinstance(minutes_remaining, int) and minutes_remaining <= 0 and addon_minutes <= 0:
                raise HTTPException(
                    status_code=429,
                    detail="You have reached your free meditation limit. Please upgrade your plan for more."
                )

    except HTTPException:
        raise
    except Exception as e:
        # If quota check fails for any reason, log and allow (don't block on system errors)
        print(f"Warning: Could not check quota before creating content: {e}")

    content_id = "<failed>"
    match request.mode:
        case ContentType.AUDIO.value:
            # Get the conversation to get the user_id
            query = select(Conversation).where(
                Conversation.id == request.conversation_id
            )
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation with id {request.conversation_id} not found",
                )

            # An identical generation already running is returned rather than
            # started again. Without this, a double-clicked Generate makes two
            # generations with two different ids, which the ledger cannot
            # recognise as duplicates because two ids are two real generations.
            running = await _existing_in_flight(
                session, conversation.user_id, request, ContentType.AUDIO
            )
            if running:
                tu.logger.info(
                    f"[CONTENT] duplicate audio request for message "
                    f"{request.message_id}; returning in-flight {running}"
                )
                return w.ContentGenerationResponse(id=running, status="processing")

            # Create ContentGeneration record immediately with processing status
            content_id = str(uuid.uuid4())
            content_generation = ContentGeneration(
                id=content_id,
                user_id=conversation.user_id,
                conversation_id=request.conversation_id,
                message_id=request.message_id,
                content_type=ContentType.AUDIO,
                content_path=None,  # Will be updated when generation completes
                transcript=None,  # Will be updated when generation completes
                voice_id="shimmer",
            )

            session.add(content_generation)
            await session.commit()

            # Debit AFTER the row exists (the ledger references it) and BEFORE
            # the work is queued, so a generation can never run unpaid. If it
            # fails, mark_content_failed refunds.
            await _charge_if_needed(session, current_user, media_decision, content_id)

            # Add audio generation to background tasks
            background_tasks.add_task(
                generate_audio_content,
                content_id,
                request.conversation_id,
                request.message_id,
                request.length,  # Pass the requested length (e.g., "5 min")
            )

        case ContentType.VIDEO.value:
            # Get the conversation to get the user_id
            query = select(Conversation).where(
                Conversation.id == request.conversation_id
            )
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation with id {request.conversation_id} not found",
                )

            # An identical generation already running is returned rather than
            # started again. Without this, a double-clicked Generate makes two
            # generations with two different ids, which the ledger cannot
            # recognise as duplicates because two ids are two real generations.
            running = await _existing_in_flight(
                session, conversation.user_id, request, ContentType.VIDEO
            )
            if running:
                tu.logger.info(
                    f"[CONTENT] duplicate video request for message "
                    f"{request.message_id}; returning in-flight {running}"
                )
                return w.ContentGenerationResponse(id=running, status="processing")

            # Create ContentGeneration record immediately with processing status
            content_id = str(uuid.uuid4())
            content_generation = ContentGeneration(
                id=content_id,
                user_id=conversation.user_id,
                conversation_id=request.conversation_id,
                message_id=request.message_id,
                content_type=ContentType.VIDEO,
                content_path=None,  # Will be updated when generation completes
                transcript=None,  # Will be updated when generation completes
                voice_id="shimmer",
            )

            session.add(content_generation)
            await session.commit()

            # Debit AFTER the row exists (the ledger references it) and BEFORE
            # the work is queued, so a generation can never run unpaid. If it
            # fails, mark_content_failed refunds.
            await _charge_if_needed(session, current_user, media_decision, content_id)

            # Add video generation to background tasks
            background_tasks.add_task(
                generate_video_content,
                content_id,
                request.conversation_id,
                request.message_id,
                request.length,  # Pass the requested length to video generation too
            )
        case ContentType.IMAGE.value:
            # Get the conversation to get the user_id
            query = select(Conversation).where(
                Conversation.id == request.conversation_id
            )
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail=f"Conversation with id {request.conversation_id} not found",
                )

            # Create ContentGeneration record immediately with processing status
            content_id = str(uuid.uuid4())
            content_generation = ContentGeneration(
                id=content_id,
                user_id=conversation.user_id,
                conversation_id=request.conversation_id,
                message_id=request.message_id,
                content_type=ContentType.IMAGE,
                content_path=None,  # Will be updated when generation completes
                cc_text=None,  # Will be updated when generation completes
                cc_theme="nature_sunset",
            )

            session.add(content_generation)
            await session.commit()

            # Add image generation to background tasks
            background_tasks.add_task(
                generate_image_content,
                content_id,
                request.conversation_id,
                request.message_id,
            )
        case _:
            raise HTTPException(
                status_code=400,
                detail="Invalid content type. Must be 'audio', 'video', or 'image'",
            )
    return w.ContentGenerationResponse(id=content_id,status="processing")


async def get_content(
    content_id: str,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_admin_client),
) -> w.ContentGeneration | w.ContentGenerationResponse:
    """GET /api/content/{id} - Get content details and download URLs"""

    try:
        content_uuid = UUID(content_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid content ID format")

    query = select(ContentGeneration).where(
        ContentGeneration.id == content_uuid,
        ContentGeneration.user_id == current_user.id,
    )
    result = await session.execute(query)
    content: ContentGeneration | None = result.scalar_one_or_none()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Trust the DB status column as source of truth. Background tasks write
    # 'complete' / 'failed' explicitly; the server default for unfinished rows
    # is 'pending'. Fall back to inferring from content_path for resilience.
    status = getattr(content, "status", None) or (
        "complete" if content.content_path else "processing"
    )
    error_message = getattr(content, "error_message", None)

    # Surface failures so the UI can show the error + Try Again button instead
    # of spinning forever.
    if status == "failed":
        return w.ContentGenerationResponse(
            id=str(content.id),
            status="failed",
            error_message=error_message,
        )

    if status == "complete" and content.content_path:
        try:
            presigned_response = spb_client.storage.from_("generations").create_signed_url(
                content.content_path, 315360000  # 10 years expiry
            )

            if presigned_response.get("error"):
                 return w.ContentGenerationResponse(id=str(content.id), status="processing")

            content_url = presigned_response.get("signedURL")
            return w.ContentGeneration(
                id=str(content.id),
                status="complete",
                conversation_id=str(content.conversation_id),
                message_id=str(content.message_id),
                content_type=content.content_type.value,
                content_url=content_url,
                created_at=content.created_at,
                transcript=content.transcript,
                error_message=None,
            )
        except Exception:
            return w.ContentGenerationResponse(id=str(content.id), status="processing")

    # pending / processing / anything else in-flight
    return w.ContentGenerationResponse(id=str(content.id), status="processing")


async def get_image_content(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_admin_client),
) -> List[w.ContentGeneration]:
    """GET /api/content/images - Get all image content for user"""
    
    offset = (page - 1) * limit
    
    query = (
        select(ContentGeneration)
        .where(
            ContentGeneration.user_id == current_user.id,
            ContentGeneration.content_type == ContentType.IMAGE
        )
        .order_by(desc(ContentGeneration.created_at))
        .offset(offset)
        .limit(limit)
    )
    
    result = await session.execute(query)
    contents = result.scalars().all()
    
    return [map_to_wire_content(c, spb_client) for c in contents]


async def get_media_content(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_admin_client),
) -> List[w.ContentGeneration]:
    """GET /api/content/media - Get all Audio/Video content for user"""
    
    offset = (page - 1) * limit
    
    query = (
        select(ContentGeneration)
        .where(
            ContentGeneration.user_id == current_user.id,
            ContentGeneration.content_type.in_([ContentType.AUDIO, ContentType.VIDEO])
        )
        .order_by(desc(ContentGeneration.created_at))
        .offset(offset)
        .limit(limit)
    )
    
    result = await session.execute(query)
    contents = result.scalars().all()
    
    return [map_to_wire_content(c, spb_client) for c in contents]


async def get_conversation_content(
    conversation_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_admin_client),
) -> List[w.ContentGeneration]:
    """GET /api/content/conversation/{conversation_id} - Get content by conversation"""
    
    # Verify user owns conversation?
    # Actually, simply checking ContentGeneration.user_id == current_user.id in the query is enough safely
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
        
    offset = (page - 1) * limit
    
    query = (
        select(ContentGeneration)
        .where(
            ContentGeneration.conversation_id == conv_uuid,
            ContentGeneration.user_id == current_user.id  # Security check
        )
        .order_by(desc(ContentGeneration.created_at))
        .offset(offset)
        .limit(limit)
    )
    
    result = await session.execute(query)
    contents = result.scalars().all()
    
    return [map_to_wire_content(c, spb_client) for c in contents]
