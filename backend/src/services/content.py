from typing import List, Optional
from fastapi import BackgroundTasks, Depends, Query, HTTPException, APIRouter
from supabase import Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID
import uuid

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
from src.content.video import generate_video_content
from src.content.audio import generate_audio_content
from src.content.image import generate_image_content

# Create helper function to map DB model to Wire model
def map_to_wire_content(content: ContentGeneration, spb_client: Client) -> w.ContentGeneration:
    status = "processing"
    content_url = None

    if content.content_path:
        status = "complete"
        try:
             # Generate presigned URL for download (expires in 1 hour)
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
    )


async def create_content(
    request: w.ContentGenerationRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_admin_client),
    current_user: UserProfile = Depends(get_current_user),
) -> w.ContentGenerationResponse:
    """POST /api/meditation/create - Generate meditation content"""

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

    if content.content_path:
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
            )
        except Exception:
            return w.ContentGenerationResponse(id=str(content.id), status="processing")
    else:
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
