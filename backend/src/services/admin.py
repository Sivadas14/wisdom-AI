from src.llm_shim import tu

from fastapi import Depends, Query, HTTPException, UploadFile, BackgroundTasks
from uuid import UUID
from supabase import Client
import hashlib
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import UploadFile, File, Depends, HTTPException, BackgroundTasks
from supabase import Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert
from uuid import uuid4
from typing import List


from src.db import get_db_session_fa, SourceDocument as DBSourceDocument, get_background_session
from src.settings import get_supabase_client
from src import wire as w


from src.db import (
    get_db_session_fa,
    UserProfile as DBUserProfile,
    SourceDocument as DBSourceDocument,
    ContentGeneration,
    Message,
    Conversation,
    ContentType,
    DocumentStatus,
    Subscription,
    UserRole,
)
from src import wire as w
from src.dependencies import get_current_user
from src.settings import get_supabase_client, get_supabase_admin_client, get_llm, get_settings, Settings
from src.chunking import extract_pdf_text
from src.db import DocumentChunk


# ============================================================================
# 1. USER MANAGEMENT
# ============================================================================


from src.services.usage import get_usage, calculate_conversation_usage

async def list_users(
    limit: int = Query(50, le=100),
    skip: int = Query(0, ge=0),
    search_term: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.ListUsersResponse:
    """GET /api/admin/users - List all users with filtering (lightweight) and pagination"""

    # Build the base query
    query = select(DBUserProfile)
    count_query = select(func.count()).select_from(DBUserProfile)

    # Apply filters: Search in name, phone, or email
    if search_term:
        search_filter = or_(
            DBUserProfile.name.ilike(f"%{search_term}%"),
            DBUserProfile.phone_number.ilike(f"%{search_term}%"),
            DBUserProfile.email_id.ilike(f"%{search_term}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_count_result = await session.execute(count_query)
    total_count = total_count_result.scalar_one()

    # Apply limit, offset and order by creation date (newest first)
    query = query.order_by(DBUserProfile.created_at.desc()).offset(skip).limit(limit)

    # Execute query
    result = await session.execute(query)
    db_users: list[DBUserProfile] = result.scalars().all()

    # create wire users
    wire_users = []

    for user in db_users:
        # Get basic wire model
        wire_user = await user.to_bm()
        
        # Get subscription status
        sub_query = (
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        sub_result = await session.execute(sub_query)
        latest_sub = sub_result.scalar_one_or_none()
        subscription_status = latest_sub.status.value if latest_sub else "No Subscription"

        # Simplified UserListItem
        wire_users.append(
            w.UserListItem(
                **wire_user.model_dump(),
                subscription_status=subscription_status,
            )
        )
    return w.ListUsersResponse(users=wire_users, total_count=total_count)


async def get_user_admin_details(
    user_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.UserWithUsage:
    """GET /api/admin/users/{user_id} - Get full details for a single user"""

    # Validate UUID format
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Get the user
    query = select(DBUserProfile).where(DBUserProfile.id == user_uuid)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get basic wire model
    wire_user = await user.to_bm()

    # Get subscription status
    sub_query = (
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub_result = await session.execute(sub_query)
    latest_sub = sub_result.scalar_one_or_none()
    subscription_status = latest_sub.status.value if latest_sub else "No Subscription"

    # Get full usage details (HEAVY)
    try:
        quota_details = await get_usage(current_user=user, session=session)
    except Exception as e:
        tu.logger.error(f"Failed to get usage for user {user.id}: {e}")
        quota_details = None

    # Calculate legacy usage_stats (HEAVY)
    conversations_count = await calculate_conversation_usage(user.id, session)
    
    content_generations_query = await session.execute(
        select(ContentGeneration).where(ContentGeneration.user_id == user.id)
    )
    content_generations = content_generations_query.scalars().all()

    return w.UserWithUsage(
        **wire_user.model_dump(),
        subscription_status=subscription_status,
        quota_details=quota_details,
        usage_stats={
            "conversations": conversations_count,
            "content_generations": {
                "total": len(content_generations),
                "video": len([c for c in content_generations if c.content_type == ContentType.VIDEO]),
                "audio": len([c for c in content_generations if c.content_type == ContentType.AUDIO]),
                "image": len([c for c in content_generations if c.content_type == ContentType.IMAGE]),
            },
        },
    )


async def delete_user(
    user_id: str,
    current_user: DBUserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_client),
    spb_admin: Client = Depends(get_supabase_admin_client),
) -> w.SuccessResponse:
    """DELETE /api/admin/users/{id} - Delete user and all data"""

    # Validate UUID format
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Check if user exists
    query = select(DBUserProfile).where(DBUserProfile.id == user_uuid)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # Log the deletion for audit purposes
    tu.logger.info(
        f"Admin {current_user.id} deleting user {user.id} ({user.phone_number})"
    )

    # delete content generations
    content_generations = await session.execute(
        select(ContentGeneration).where(ContentGeneration.user_id == user.id)
    )
    content_generations = content_generations.scalars().all()
    if content_generations:
        for content_generation in content_generations:
            if content_generation.content_path:
                spb_client.storage.from_("generations").remove(
                    [content_generation.content_path]
                )
                tu.logger.info(
                    f"Deleted file from storage: {content_generation.content_path}"
                )
            await session.delete(content_generation)

    # Delete from Supabase Auth if auth_user_id exists
    if user.auth_user_id:
        try:
            spb_admin.auth.admin.delete_user(str(user.auth_user_id))
            tu.logger.info(f"Deleted user from Supabase Auth: {user.auth_user_id}")
        except Exception as e:
            tu.logger.error(f"Failed to delete user from Supabase Auth: {e}")
            # We continue even if auth deletion fails, as the DB record is the primary one we want to remove

    await session.delete(user)  # Delete the user (cascading will handle related data)

    tu.logger.info(f"Successfully deleted user {user.id} and all associated data")
    return w.SuccessResponse(
        success=True,
        message=f"User {user.phone_number} and all associated data deleted successfully",
    )

async def toggle_user_active(
    user_id: str,
    current_user: DBUserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SuccessResponse:
    """PATCH /api/admin/users/{user_id}/toggle-active - Toggle user active status"""

    # Validate UUID format
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Check if user exists
    query = select(DBUserProfile).where(DBUserProfile.id == user_uuid)
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deactivating themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    # Toggle active status
    user.is_active = not user.is_active
    new_status = "active" if user.is_active else "inactive"

    tu.logger.info(
        f"Admin {current_user.id} toggled user {user.id} to {new_status}"
    )

    return w.SuccessResponse(
        success=True,
        message=f"User {user.phone_number or user.email_id} is now {new_status}",
        data={"is_active": user.is_active},
    )


# ============================================================================
# 2. CONTENT GENERATION
# ============================================================================


async def delete_content(
    content_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_client),
) -> w.SuccessResponse:
    """DELETE /api/admin/content/{type}/{id} - Remove generated content"""

    # Validate UUID format
    try:
        content_uuid = UUID(content_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid content ID format")

    # Find the content generation record
    query = select(ContentGeneration).where(ContentGeneration.id == content_uuid)
    result = await session.execute(query)
    content: ContentGeneration | None = result.scalar_one_or_none()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Log the deletion for audit purposes
    tu.logger.info(f"Deleting {content.content_type} content {content.id}")

    # TODO: Delete associated files from Supabase storage
    if content.content_path:
        try:
            # Delete from Supabase storage
            spb_client.storage.from_("generations").remove([content.content_path])
            tu.logger.info(f"Deleted file from storage: {content.content_path}")
        except Exception as e:
            tu.logger.warning(f"Failed to delete file from storage: {e}")

    # Delete the content generation record
    await session.delete(content)
    # Note: session.commit() is handled automatically by the session dependency

    tu.logger.info(f"Successfully deleted {content.content_type} content {content.id}")

    return w.SuccessResponse(
        success=True,
        message=f"{content.id} {content.content_type.value} content deleted successfully",
    )


# ============================================================================
# 3. FEEDBACK
# ============================================================================


async def get_feedback(
    limit: int = Query(50, le=100),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.AdminFeedbackResponse:
    """GET /api/admin/feedback - Get user feedback"""

    # Build query to get all messages with feedback, joining through conversations
    query = (
        select(Message, DBUserProfile)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(DBUserProfile, Conversation.user_id == DBUserProfile.id)
        .where(Message.feedback_type.is_not(None))
        .order_by(Message.feedback_given_at.desc())
        .limit(limit)
    )

    # Execute the query
    result = await session.execute(query)
    feedback_data: list[tuple[Message, DBUserProfile]] = result.all()

    # Convert to UserFeedback objects
    feedback_list = []
    for message, user in feedback_data:
        user_feedback = w.UserFeedback(
            user_id=str(user.id),
            message_id=str(message.id),
            type=message.feedback_type.value,
            comment=message.feedback_comment,
            created_at=message.feedback_given_at,
        )
        feedback_list.append(user_feedback)

    return w.AdminFeedbackResponse(feedback=feedback_list)


# ============================================================================
# 4. SOURCE DATA
# ============================================================================


async def list_source_data(
    limit: int = Query(50, le=100),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.SourceDocumentsResponse:
    """GET /api/admin/source-data/list - List uploaded files"""

    query = (
        select(DBSourceDocument)
        .order_by(DBSourceDocument.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    source_documents: list[DBSourceDocument] = result.scalars().all()

    return w.SourceDocumentsResponse(
        files=[await source_document.to_bm() for source_document in source_documents]
    )




# ============================================================================
# 4. DELETE SOURCE DOCUMENT
# ============================================================================

async def delete_source_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_admin_client),
):
    """
    Delete a source document and all its chunks.
    Also removes the file from Supabase Storage (best-effort).
    """
    result = await session.execute(
        select(DBSourceDocument).where(DBSourceDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    filename = doc.filename

    # Delete DB record (cascade removes all chunks automatically)
    await session.delete(doc)
    await session.commit()
    tu.logger.info(f"[DELETE_DOC] Deleted document {document_id} ({filename}) and its chunks")

    # Best-effort: remove from Supabase Storage (don't fail if missing)
    try:
        spb_client.storage.from_("source-files").remove([filename])
        tu.logger.info(f"[DELETE_DOC] Removed {filename} from Supabase Storage")
    except Exception as e:
        tu.logger.warning(f"[DELETE_DOC] Storage remove failed (non-fatal): {e}")

    return {"success": True, "message": f"Deleted '{filename}' and all its indexed passages."}


# ============================================================================
# 5. UPLOAD  DATA
# ============================================================================

async def _index_pdf_background(
    file_id: uuid4,
    filename: str,
    content: bytes,
):
    """
    Background task: extract text, generate embeddings, save chunks.
    Runs AFTER the HTTP response has been sent so there is no timeout risk.
    """
    tu.logger.info(f"[INDEX_BG] Starting background indexing for {filename} (id={file_id})")
    try:
        chunks = await extract_pdf_text(content)
        tu.logger.info(f"[INDEX_BG] Extracted {len(chunks)} chunks from {filename}")

        # Verse-aware regrouping for numbered works (Upadesa Saram, Ulladu
        # Narpadu). Page chunks carry no verse label, so "verse 21" has nothing
        # to match on and retrieval falls back to the contents page. Regrouping
        # by verse puts the number in both the label and the embedded text.
        # Returns None for anything unrecognised, in which case the ordinary
        # page chunks are kept.
        try:
            from src.verse_index import regroup_by_verse
            regrouped = regroup_by_verse(chunks, filename)
            if regrouped:
                tu.logger.info(
                    f"[INDEX_BG] Verse-aware chunking applied to {filename}: "
                    f"{len(chunks)} pages -> {len(regrouped)} chunks"
                )
                chunks = regrouped
        except Exception as e:
            # Never let this cost us the whole document.
            tu.logger.error(f"[INDEX_BG] Verse regrouping failed for {filename}: {e}")

        if chunks:
            model = get_llm()
            saved = 0
            failed = 0
            async with get_background_session() as bg_session:
                for chunk in chunks:
                    try:
                        embedding_response = await model.embedding_async(
                            chunk.content, model="text-embedding-3-small"
                        )
                        embedding_vector = embedding_response.embedding[0]
                        db_chunk = DocumentChunk(
                            id=uuid4(),
                            source_document_id=file_id,
                            content=chunk.content,
                            embedding=embedding_vector,
                            location=chunk.loc,
                            model_used="text-embedding-3-small",
                        )
                        bg_session.add(db_chunk)
                        saved += 1
                    except Exception as e:
                        tu.logger.error(f"[INDEX_BG] Chunk embed failed: {e}")
                        failed += 1
                        continue

                # Mark document COMPLETED
                result = await bg_session.execute(
                    select(DBSourceDocument).where(DBSourceDocument.id == file_id)
                )
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = DocumentStatus.COMPLETED
                await bg_session.commit()
            tu.logger.info(f"[INDEX_BG] Done {filename}: {saved} chunks saved, {failed} failed")
        else:
            # No chunks — still mark completed
            async with get_background_session() as bg_session:
                result = await bg_session.execute(
                    select(DBSourceDocument).where(DBSourceDocument.id == file_id)
                )
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = DocumentStatus.COMPLETED
                await bg_session.commit()
            tu.logger.warning(f"[INDEX_BG] No chunks extracted from {filename}")

    except Exception as e:
        tu.logger.error(f"[INDEX_BG] Fatal error for {filename}: {e}")
        # Mark document FAILED so admin can see it in the UI
        try:
            async with get_background_session() as bg_session:
                result = await bg_session.execute(
                    select(DBSourceDocument).where(DBSourceDocument.id == file_id)
                )
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = DocumentStatus.FAILED
                await bg_session.commit()
        except Exception as inner:
            tu.logger.error(f"[INDEX_BG] Could not mark FAILED: {inner}")


# @router.post("/upload", response_model=w.SourceDocument)
async def upload_source_pdfs(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_admin_client),
):
    """
    Upload PDFs: saves file + creates DB record immediately (status=PROCESSING),
    then indexes embeddings in the background so the request never times out.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    created_docs = []

    for file in files:
        # 1. Validate type
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400, detail=f"Invalid file type: {file.filename}"
            )

        # 2. Read content
        file_id = uuid4()
        stored_filename = file.filename
        content = await file.read()
        file_size = len(content)

        # 3. Upload to Supabase Storage
        try:
            spb_client.storage.from_("source-files").upload(
                stored_filename,
                content,
                {"content-type": "application/pdf", "upsert": "true"},
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Upload failed for {file.filename}: {str(e)}",
            )

        # 4. Create DB record with PROCESSING status — commit immediately
        db_record = DBSourceDocument(
            id=file_id,
            filename=stored_filename,
            file_size_bytes=file_size,
            active=True,
            status=DocumentStatus.PROCESSING,
        )
        session.add(db_record)
        created_docs.append((db_record, content))

    # Commit all records before scheduling background work
    await session.commit()

    # 5. Schedule background indexing for each file (runs after response returns)
    for db_record, content in created_docs:
        background_tasks.add_task(
            _index_pdf_background,
            file_id=db_record.id,
            filename=db_record.filename,
            content=content,
        )
        tu.logger.info(f"[UPLOAD] Queued background indexing for {db_record.filename}")

    # 6. Return immediately — status will show PROCESSING in the UI
    return [await doc.to_bm() for doc, _ in created_docs]


# ============================================================================
# 6. ADMIN BOOTSTRAP — promote a user to ADMIN role
# ============================================================================

from pydantic import BaseModel as PydanticBaseModel
from fastapi.responses import JSONResponse

class MakeAdminRequest(PydanticBaseModel):
    email: str
    admin_secret: str


async def make_admin(
    request: MakeAdminRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> JSONResponse:
    """POST /api/admin/make-admin

    Promotes a user to ADMIN role.  Protected by a shared secret configured
    via the ASAM_ADMIN_SECRET environment variable in App Runner.

    This endpoint is intentionally unauthenticated so the very first admin
    can bootstrap their account without needing to already be logged in.
    """
    # Verify secret — call get_settings() directly, no Depends needed
    cfg = get_settings()
    if request.admin_secret != cfg.admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    # Find user by email
    try:
        query = select(DBUserProfile).where(DBUserProfile.email_id == request.email).limit(5)
        result = await session.execute(query)
        users = result.scalars().all()
        user = users[0] if users else None
        tu.logger.info(f"[MAKE_ADMIN] Found {len(users)} profile(s) for {request.email}")
    except Exception as e:
        tu.logger.error(f"[MAKE_ADMIN] DB query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"No user found with email '{request.email}'. Sign in once via the normal login page first, then retry."
        )

    try:
        promoted = 0
        for u in users:
            if u.role != UserRole.ADMIN:
                u.role = UserRole.ADMIN
                promoted += 1
                tu.logger.info(f"[BOOTSTRAP] Promoted {request.email} (id={u.id}) to ADMIN")
        await session.commit()
    except Exception as e:
        await session.rollback()
        tu.logger.error(f"[MAKE_ADMIN] Commit failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update role: {str(e)}")

    if promoted == 0:
        return JSONResponse({"success": True, "message": f"{request.email} is already an ADMIN on all {len(users)} profile(s)."})

    tu.logger.info(f"[BOOTSTRAP] Done — promoted {promoted} of {len(users)} profile(s)")
    return JSONResponse({
        "success": True,
        "message": f"Success — {request.email} has been promoted to ADMIN. You can now sign in via /admin/login."
    })


# ============================================================================
# 7. SUGGESTED TOPICS — admin review of novel user-question topics
# ============================================================================

from sqlalchemy import text as sa_text

class UpdateSuggestedTopicRequest(PydanticBaseModel):
    status: str          # "approved" | "rejected"
    label: str | None = None   # Admin can rename the label
    tab: str | None = None     # Admin can override tab assignment


async def list_suggested_topics(
    status: str | None = Query(None, description="Filter by status: pending|approved|rejected"),
    session: AsyncSession = Depends(get_db_session_fa),
) -> JSONResponse:
    """GET /api/admin/suggested-topics — list topic suggestions, pending first."""
    if status:
        result = await session.execute(
            sa_text(
                "SELECT id, created_at, label, question, tab, status, occurrence_count "
                "FROM suggested_topics WHERE status = :status "
                "ORDER BY occurrence_count DESC, created_at DESC"
            ),
            {"status": status},
        )
    else:
        result = await session.execute(
            sa_text(
                "SELECT id, created_at, label, question, tab, status, occurrence_count "
                "FROM suggested_topics "
                "ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, "
                "occurrence_count DESC, created_at DESC"
            )
        )
    rows = result.fetchall()
    items = [
        {
            "id": str(r.id),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "label": r.label,
            "question": r.question,
            "tab": r.tab,
            "status": r.status,
            "occurrence_count": r.occurrence_count,
        }
        for r in rows
    ]
    return JSONResponse({"items": items, "total": len(items)})


async def update_suggested_topic(
    topic_id: str,
    request: UpdateSuggestedTopicRequest,
    session: AsyncSession = Depends(get_db_session_fa),
) -> JSONResponse:
    """PATCH /api/admin/suggested-topics/{topic_id} — approve or reject a topic."""
    if request.status not in ("approved", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="status must be 'approved', 'rejected', or 'pending'")

    # Build update dynamically
    updates = {"status": request.status, "id": topic_id}
    set_clauses = ["status = :status"]
    if request.label:
        set_clauses.append("label = :label")
        updates["label"] = request.label
    if request.tab:
        if request.tab not in ("teachings", "personal"):
            raise HTTPException(status_code=400, detail="tab must be 'teachings' or 'personal'")
        set_clauses.append("tab = :tab")
        updates["tab"] = request.tab

    sql = f"UPDATE suggested_topics SET {', '.join(set_clauses)} WHERE id = :id RETURNING id"
    result = await session.execute(sa_text(sql), updates)
    updated = result.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Suggested topic not found")
    await session.commit()
    return JSONResponse({"success": True, "status": request.status})


async def get_dynamic_topics(
    session: AsyncSession = Depends(get_db_session_fa),
) -> JSONResponse:
    """GET /api/topics/dynamic — public endpoint: returns admin-approved dynamic topics."""
    result = await session.execute(
        sa_text(
            "SELECT label, question, tab FROM suggested_topics "
            "WHERE status = 'approved' ORDER BY occurrence_count DESC, created_at DESC"
        )
    )
    rows = result.fetchall()
    items = [{"label": r.label, "question": r.question, "tab": r.tab} for r in rows]
    return JSONResponse({"items": items})


# ─────────────────────────────────────────────────────────────────────────────
# Corpus integrity: audit and in-place re-index
#
# Indexing embeds chunk by chunk and skips failures so one bad chunk cannot
# abort a whole book. The cost is that a document which extracts no text is
# saved with status "completed" and ZERO chunks: it looks perfectly healthy in
# the admin list and is invisible to search. An audit of the live corpus found
# 30 of 50 documents in exactly that state, including the Collected Works.
#
# `audit_corpus` reports what is actually retrievable. `reindex_source_document`
# rebuilds one document's chunks IN PLACE from the copy already in storage, so
# fixing a document does not create a duplicate the way re-uploading does.
# ─────────────────────────────────────────────────────────────────────────────

async def economics_report(
    session: AsyncSession = Depends(get_db_session_fa),
):
    """GET /api/admin/economics — is the model working?

    The question this exists to answer: does making Wisdom free grow use
    enough, and do credits and patronage cover what that use costs? Every
    figure is computed from the database now, not accumulated in a counter
    that can drift.

    Costs are estimates from measured unit prices (chat ~Rs 0.66/answer,
    media ~Rs 1.50/min at Rs 12.01 per 5-min credit). Infrastructure is an
    env var (ASAM_MONTHLY_INFRA_INR) because nothing in this codebase can see
    the AWS invoice; the report says so rather than pretending.
    """
    import datetime as _dt
    import os as _os

    from sqlalchemy import text as _sql

    month_start = _dt.datetime.now(_dt.timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    async def _one(query, **params):
        return (await session.execute(_sql(query), params)).first()

    msgs = await _one(
        "SELECT COUNT(*) FROM messages WHERE role='assistant' AND created_at >= :m",
        m=month_start)
    askers = await _one(
        """SELECT COUNT(DISTINCT c.user_id) FROM messages msg
             JOIN conversations c ON c.id = msg.conversation_id
            WHERE msg.created_at >= :m""", m=month_start)
    media = (await session.execute(_sql(
        """SELECT content_type, COUNT(*), COALESCE(SUM(duration_seconds),0)
             FROM content_generations WHERE created_at >= :m
            GROUP BY content_type"""), {"m": month_start})).all()
    credits_sold = await _one(
        """SELECT COALESCE(SUM(credits),0), COALESCE(SUM(amount_minor),0)
             FROM credit_purchases WHERE status='paid' AND created_at >= :m
              AND currency='INR'""", m=month_start)
    credits_sold_usd = await _one(
        """SELECT COALESCE(SUM(credits),0), COALESCE(SUM(amount_minor),0)
             FROM credit_purchases WHERE status='paid' AND created_at >= :m
              AND currency='USD'""", m=month_start)
    consumed = await _one(
        """SELECT COALESCE(-SUM(delta),0) FROM credit_transactions
            WHERE kind='MEDIA_DEBIT' AND created_at >= :m""", m=month_start)
    refunded = await _one(
        """SELECT COALESCE(SUM(delta),0) FROM credit_transactions
            WHERE kind='REFUND' AND created_at >= :m""", m=month_start)
    liability = await _one("SELECT COALESCE(SUM(balance),0) FROM credit_wallets")

    answers = int(msgs[0] if msgs else 0)
    media_rows = {str(r[0]): {"count": int(r[1]), "seconds": int(r[2])} for r in media}
    media_minutes = sum(v["seconds"] for v in media_rows.values()) / 60

    CHAT_COST_INR = 0.66
    MEDIA_COST_PER_MIN_INR = 12.01 / 5
    chat_cost = round(answers * CHAT_COST_INR, 2)
    media_cost = round(media_minutes * MEDIA_COST_PER_MIN_INR, 2)
    infra = float(_os.getenv("ASAM_MONTHLY_INFRA_INR", "0") or 0)
    revenue_inr = (credits_sold[1] or 0) / 100
    revenue_usd = (credits_sold_usd[1] or 0) / 100

    # Reconciliation: the one number that must always be zero rows.
    from src.services.credits import reconcile
    drift = await reconcile(session)

    return {
        "month_start": month_start.isoformat(),
        "wisdom": {"answers": answers, "unique_askers": int(askers[0] if askers else 0),
                   "estimated_cost_inr": chat_cost},
        "media": {"by_type": media_rows, "minutes": round(media_minutes, 1),
                  "estimated_cost_inr": media_cost},
        "credits": {
            "sold_inr": {"credits": int(credits_sold[0] or 0), "revenue": revenue_inr},
            "sold_usd": {"credits": int(credits_sold_usd[0] or 0), "revenue": revenue_usd},
            "consumed": int(consumed[0] if consumed else 0),
            "refunded": int(refunded[0] if refunded else 0),
            "unspent_liability": int(liability[0] if liability else 0),
        },
        "costs": {
            "chat_inr": chat_cost,
            "media_inr": media_cost,
            "infrastructure_inr": infra,
            "infrastructure_note": (
                None if infra else
                "ASAM_MONTHLY_INFRA_INR is unset; total excludes the fixed floor."
            ),
            "total_inr": round(chat_cost + media_cost + infra, 2),
        },
        "contribution_inr": round(revenue_inr + revenue_usd * 88 - chat_cost - media_cost - infra, 2),
        "ledger_drift": drift,
    }


async def audit_corpus(
    session: AsyncSession = Depends(get_db_session_fa),
):
    """GET /api/admin/source-data/audit — what is actually in the corpus.

    Status alone is not evidence: a document can read "completed" and hold
    nothing. This counts real chunks per document.
    """
    rows = (await session.execute(
        select(
            DBSourceDocument.id,
            DBSourceDocument.filename,
            DBSourceDocument.status,
            DBSourceDocument.active,
            func.count(DocumentChunk.id).label("chunks"),
        )
        .outerjoin(DocumentChunk,
                   DocumentChunk.source_document_id == DBSourceDocument.id)
        .group_by(DBSourceDocument.id, DBSourceDocument.filename,
                  DBSourceDocument.status, DBSourceDocument.active)
        .order_by(func.count(DocumentChunk.id).asc())
    )).all()

    docs = [
        {
            "id": str(r.id),
            "filename": r.filename,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "active": r.active,
            "chunks": int(r.chunks or 0),
        }
        for r in rows
    ]
    # Chunk counts alone cannot prove two records hold the same book: two
    # different translations can chunk to the same length by coincidence, and
    # the same book uploaded twice under different filenames looks like two
    # works. Fingerprint the actual text so duplicates are identified by
    # content, not by guessing from titles.
    #
    # Hashed in Python, not in SQL. Postgres can do this with string_agg, but
    # the aggregate has to be given an explicit sort and an explicit separator
    # type, and getting that wrong takes the whole audit down with a 500 —
    # which is exactly what the audit is for. Pulling prefixes and hashing here
    # is a few megabytes of transfer and cannot fail in an interesting way.
    #
    # Sorted by content, NOT by chunk id: ids are generated at index time, so
    # under id order the same book uploaded twice would hash differently and
    # the duplicate would hide.
    fingerprint_error = None
    try:
        fp_rows = (await session.execute(
            select(
                DocumentChunk.source_document_id,
                DocumentChunk.content,
            )
        )).all()
        acc: dict[str, list] = {}
        for doc_id, content in fp_rows:
            body = content or ""
            entry = acc.setdefault(str(doc_id), [0, []])
            entry[0] += len(body)
            entry[1].append(body[:400])
        for d in docs:
            entry = acc.get(d["id"])
            if entry is None:
                d["chars"], d["digest"] = 0, None
                continue
            d["chars"] = entry[0]
            d["digest"] = hashlib.md5(
                "".join(sorted(entry[1])).encode("utf-8", "replace")
            ).hexdigest()
    except Exception as exc:  # noqa: BLE001 - the audit must still answer
        fingerprint_error = f"{type(exc).__name__}: {exc}"
        for d in docs:
            d.setdefault("chars", 0)
            d.setdefault("digest", None)

    empty = [d for d in docs if d["chunks"] == 0]
    return {
        "documents": len(docs),
        "with_chunks": len(docs) - len(empty),
        "empty": len(empty),
        "total_chunks": sum(d["chunks"] for d in docs),
        "fingerprint_error": fingerprint_error,
        "empty_documents": empty,
        "all": docs,
    }


async def reindex_source_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_admin_client),
):
    """POST /api/admin/source-data/{id}/reindex — rebuild chunks in place.

    Downloads the copy already in storage and re-runs extraction, so a document
    can be repaired without re-uploading it and without creating a duplicate.
    Existing chunks are replaced only if the new extraction produces some; a
    failed re-extraction leaves the current chunks untouched.
    """
    doc = (await session.execute(
        select(DBSourceDocument).where(DBSourceDocument.id == document_id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        content = spb_client.storage.from_("source-files").download(doc.filename)
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Could not read '{doc.filename}' from storage: {e}",
        )

    background_tasks.add_task(
        _reindex_background, document_id, doc.filename, content
    )
    return {
        "success": True,
        "message": f"Re-indexing '{doc.filename}' ({len(content) // 1024} KB) in the background.",
    }


async def _reindex_background(file_id: UUID, filename: str, content: bytes):
    """Re-extract, re-embed and REPLACE a document's chunks."""
    from sqlalchemy import delete as sql_delete

    tu.logger.info(f"[REINDEX] Starting for {filename} ({file_id})")
    try:
        chunks = await extract_pdf_text(content)
        tu.logger.info(f"[REINDEX] {filename}: extracted {len(chunks)} page chunks")

        if not chunks:
            # Almost always a scan with no text layer. Say so plainly instead of
            # quietly leaving the document empty again.
            tu.logger.error(
                f"[REINDEX] {filename}: extraction produced NOTHING. The PDF "
                f"most likely has no text layer (a scan) and needs OCR before "
                f"it can be indexed. Existing chunks left untouched."
            )
            return

        try:
            from src.verse_index import regroup_by_verse
            regrouped = regroup_by_verse(chunks, filename)
            if regrouped:
                tu.logger.info(
                    f"[REINDEX] {filename}: verse-aware chunking, "
                    f"{len(chunks)} pages -> {len(regrouped)} chunks"
                )
                chunks = regrouped
        except Exception as e:
            tu.logger.error(f"[REINDEX] {filename}: verse regrouping failed: {e}")

        model = get_llm()
        saved = failed = 0
        async with get_background_session() as bg:
            # Only clear the old chunks once we know we have replacements.
            await bg.execute(
                sql_delete(DocumentChunk).where(
                    DocumentChunk.source_document_id == file_id
                )
            )
            for chunk in chunks:
                try:
                    emb = await model.embedding_async(
                        chunk.content, model="text-embedding-3-small"
                    )
                    bg.add(DocumentChunk(
                        id=uuid4(),
                        source_document_id=file_id,
                        content=chunk.content,
                        embedding=emb.embedding[0],
                        location=chunk.loc,
                        model_used="text-embedding-3-small",
                    ))
                    saved += 1
                except Exception as e:
                    failed += 1
                    tu.logger.error(f"[REINDEX] {filename}: chunk embed failed: {e}")
            await bg.commit()

        tu.logger.info(
            f"[REINDEX] {filename}: DONE, {saved} chunks saved, {failed} failed"
        )
    except Exception as e:
        tu.logger.error(f"[REINDEX] {filename}: FAILED: {e}", exc_info=True)


async def set_source_document_active(
    document_id: UUID,
    active: bool = Query(..., description="true to include in search, false to retire"),
    session: AsyncSession = Depends(get_db_session_fa),
):
    """PATCH /api/admin/source-data/{id}/active — include or retire a document.

    Retrieval filters on `active`, so this removes a superseded or duplicate
    document from search without destroying its chunks.
    """
    doc = (await session.execute(
        select(DBSourceDocument).where(DBSourceDocument.id == document_id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.active = active
    await session.commit()
    tu.logger.info(f"[SET_ACTIVE] {doc.filename} -> active={active}")
    return {"success": True, "filename": doc.filename, "active": active}
