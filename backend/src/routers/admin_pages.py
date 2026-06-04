"""Admin CRUD for public content pages (the `pages` table).

Protected automatically by the existing ADMIN_AUTH middleware (it gates every
/api/admin/* path). Lets an admin create / edit / publish / delete the public
SEO content pages from the admin panel. Operates only on the `pages` table.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session_fa

router = APIRouter(prefix="/api/admin/pages", tags=["admin", "pages"])


class PageIn(BaseModel):
    slug: str
    title: str
    body: str
    meta_description: Optional[str] = None
    og_image: Optional[str] = None
    canonical_path: Optional[str] = None
    metadata: Optional[dict] = None
    lang: str = "en"
    source_url: Optional[str] = None
    published: bool = False


@router.get("")
async def list_pages(session: AsyncSession = Depends(get_db_session_fa)):
    rows = (await session.execute(sql_text(
        "SELECT slug, title, published, last_updated::text AS last_updated "
        "FROM pages ORDER BY slug"))).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{slug:path}")
async def get_page(slug: str, session: AsyncSession = Depends(get_db_session_fa)):
    row = (await session.execute(sql_text(
        "SELECT slug,title,body,meta_description,og_image,canonical_path,"
        "metadata,lang,source_url,published,last_updated::text AS last_updated "
        "FROM pages WHERE slug=:s LIMIT 1"), {"s": slug})).mappings().one_or_none()
    if not row:
        raise HTTPException(404, "Page not found")
    return dict(row)


@router.post("")
async def create_or_update_page(page: PageIn, session: AsyncSession = Depends(get_db_session_fa)):
    canonical = page.canonical_path or "/" + page.slug
    await session.execute(sql_text("""
        INSERT INTO pages (slug,title,body,meta_description,og_image,canonical_path,
                           metadata,lang,source_url,published)
        VALUES (:slug,:title,:body,:meta_description,:og_image,:canonical_path,
                CAST(:metadata AS jsonb),:lang,:source_url,:published)
        ON CONFLICT (slug) DO UPDATE SET
            title=EXCLUDED.title, body=EXCLUDED.body,
            meta_description=EXCLUDED.meta_description, og_image=EXCLUDED.og_image,
            canonical_path=EXCLUDED.canonical_path, metadata=EXCLUDED.metadata,
            lang=EXCLUDED.lang, source_url=EXCLUDED.source_url, published=EXCLUDED.published,
            last_updated=timezone('UTC', now())
    """), {**page.model_dump(exclude={"metadata", "canonical_path"}),
           "canonical_path": canonical,
           "metadata": json.dumps(page.metadata or {})})
    await session.commit()
    return {"ok": True, "slug": page.slug}


@router.put("/{slug:path}")
async def update_page(slug: str, page: PageIn, session: AsyncSession = Depends(get_db_session_fa)):
    page.slug = slug
    return await create_or_update_page(page, session)


@router.patch("/{slug:path}/publish")
async def toggle_publish(slug: str, published: bool, session: AsyncSession = Depends(get_db_session_fa)):
    res = await session.execute(sql_text(
        "UPDATE pages SET published=:p, last_updated=timezone('UTC', now()) WHERE slug=:s"),
        {"p": published, "s": slug})
    await session.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "Page not found")
    return {"ok": True, "slug": slug, "published": published}


@router.delete("/{slug:path}")
async def delete_page(slug: str, session: AsyncSession = Depends(get_db_session_fa)):
    res = await session.execute(sql_text("DELETE FROM pages WHERE slug=:s"), {"s": slug})
    await session.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "Page not found")
    return {"ok": True, "deleted": slug}
