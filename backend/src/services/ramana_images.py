"""
Admin API for managing the Ramana Maharshi image repository.
Images uploaded here are used for contemplation cards in place of AI-generated images.
"""

import asyncio
import uuid
from io import BytesIO
from functools import partial

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session_fa, RamanaImage
from src.settings import get_supabase_admin_client, get_settings

router = APIRouter(prefix="/api/admin/ramana-images", tags=["admin"])

ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
STORAGE_FOLDER = "ramana-library"
BUCKET = "generations"


# ---------------------------------------------------------------------------
# GET /api/admin/ramana-images  — list all images with signed preview URLs
# ---------------------------------------------------------------------------
@router.get("")
async def list_ramana_images(
    session: AsyncSession = Depends(get_db_session_fa),
):
    result = await session.execute(
        select(RamanaImage).order_by(RamanaImage.created_at.desc())
    )
    images = result.scalars().all()

    settings = get_settings()
    spb = get_supabase_admin_client(settings)

    items = []
    for img in images:
        try:
            signed = spb.storage.from_(BUCKET).create_signed_url(
                img.storage_path, 3600  # 1-hour preview URL
            )
            preview_url = signed.get("signedURL") or signed.get("signedUrl", "")
        except Exception:
            preview_url = ""

        items.append({
            "id": str(img.id),
            "filename": img.filename,
            "description": img.description,
            "active": img.active,
            "storage_path": img.storage_path,
            "preview_url": preview_url,
            "created_at": img.created_at.isoformat() if img.created_at else None,
        })

    active_count = sum(1 for i in items if i["active"])
    return {"images": items, "total": len(items), "active": active_count}


# ---------------------------------------------------------------------------
# POST /api/admin/ramana-images  — upload one or more images
# ---------------------------------------------------------------------------
@router.post("")
async def upload_ramana_images(
    files: list[UploadFile] = File(...),
    description: str = Form(""),
    session: AsyncSession = Depends(get_db_session_fa),
):
    settings = get_settings()
    spb = get_supabase_admin_client(settings)

    uploaded = []
    errors = []

    loop = asyncio.get_event_loop()

    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            errors.append(f"{file.filename}: unsupported type {file.content_type}")
            continue

        try:
            file_bytes = await file.read()
            ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
            storage_path = f"{STORAGE_FOLDER}/{uuid.uuid4()}.{ext}"

            # Run synchronous Supabase upload in thread pool to avoid blocking event loop
            await loop.run_in_executor(
                None,
                partial(
                    spb.storage.from_(BUCKET).upload,
                    storage_path,
                    file_bytes,
                    {"content-type": file.content_type},
                ),
            )

            img_record = RamanaImage(
                filename=file.filename,
                storage_path=storage_path,
                description=description.strip() or None,
                active=True,
            )
            session.add(img_record)
            await session.flush()  # get the id
            uploaded.append({"id": str(img_record.id), "filename": file.filename})

        except Exception as e:
            errors.append(f"{file.filename}: upload failed — {e}")

    await session.commit()
    return {"uploaded": uploaded, "errors": errors}


# ---------------------------------------------------------------------------
# PATCH /api/admin/ramana-images/{id}/toggle  — activate / deactivate
# ---------------------------------------------------------------------------
@router.patch("/{image_id}/toggle")
async def toggle_ramana_image(
    image_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
):
    result = await session.execute(
        select(RamanaImage).where(RamanaImage.id == image_id)
    )
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    img.active = not img.active
    session.add(img)
    await session.commit()
    return {"id": image_id, "active": img.active}


# ---------------------------------------------------------------------------
# DELETE /api/admin/ramana-images/{id}  — remove from storage + DB
# ---------------------------------------------------------------------------
@router.delete("/{image_id}")
async def delete_ramana_image(
    image_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
):
    result = await session.execute(
        select(RamanaImage).where(RamanaImage.id == image_id)
    )
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    storage_path = img.storage_path

    # Remove from Supabase storage
    try:
        settings = get_settings()
        spb = get_supabase_admin_client(settings)
        spb.storage.from_(BUCKET).remove([storage_path])
    except Exception as e:
        # Log but don't fail — still remove the DB record
        print(f"[RAMANA_IMAGES] Storage delete failed for {storage_path}: {e}")

    await session.delete(img)
    await session.commit()
    return {"deleted": image_id}
