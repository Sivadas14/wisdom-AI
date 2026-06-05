"""
Admin: translate -> review -> approve -> cache workflow for content pages.

Only APPROVED (reviewed) translations are ever served on the public site
(see catch_all + content_i18n.get_served_translation). Protected by the
existing ADMIN_AUTH middleware (gates all /api/admin/*). Operates on the
page_translations cache (resource_type 'contentpage_v2').
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_session_fa
from src.translation import PHASE_1_LANGS
from src.content_pages import get_published_page
from src.content_i18n import translate_content_page, LANG_DISPLAY

router = APIRouter(prefix="/api/admin/translations", tags=["admin", "translations"])
_RT = "contentpage_v2"
_LANGS = [c for c, _ in LANG_DISPLAY if c != "en"]
_NAME = dict(LANG_DISPLAY)


def _unpack(ttl: Optional[str]):
    ttl = ttl or ""
    if "\x1f" in ttl:
        t, s = ttl.split("\x1f", 1)
        return t, s
    return ttl, None


class LangBody(BaseModel):
    slug: str
    lang: str


class EditBody(BaseModel):
    slug: str
    lang: str
    title: str
    subtitle: Optional[str] = None
    body: str


@router.get("")
async def status(slug: str = Query(...), session: AsyncSession = Depends(get_db_session_fa)):
    """Status of every language for one page + the English source."""
    page = await get_published_page(session, slug)
    if not page:
        raise HTTPException(404, "Page not found")
    rows = (await session.execute(sql_text(
        "SELECT language_code, reviewed FROM page_translations "
        "WHERE domain='coin' AND resource_type=:rt AND resource_id=:s"
    ), {"rt": _RT, "s": slug})).all()
    state = {r[0]: ("approved" if r[1] else "draft") for r in rows}
    langs = [{"code": c, "name": _NAME[c], "status": state.get(c, "none")} for c in _LANGS]
    md = page.get("metadata") or {}
    return {
        "slug": slug,
        "source": {"title": page["title"],
                   "subtitle": md.get("subtitle") if isinstance(md, dict) else None,
                   "body": page["body"]},
        "languages": langs,
    }


@router.get("/one")
async def get_one(slug: str = Query(...), lang: str = Query(...),
                  session: AsyncSession = Depends(get_db_session_fa)):
    """Fetch the current draft/approved translation for editing."""
    row = (await session.execute(sql_text(
        "SELECT translated_title, translated_body, reviewed FROM page_translations "
        "WHERE domain='coin' AND resource_type=:rt AND resource_id=:s AND language_code=:l LIMIT 1"
    ), {"rt": _RT, "s": slug, "l": lang})).first()
    if not row:
        return {"slug": slug, "lang": lang, "status": "none", "title": None, "subtitle": None, "body": None}
    title, subtitle = _unpack(row[0])
    return {"slug": slug, "lang": lang, "status": ("approved" if row[2] else "draft"),
            "title": title, "subtitle": subtitle, "body": row[1]}


@router.post("/draft")
async def make_draft(b: LangBody, session: AsyncSession = Depends(get_db_session_fa)):
    """Auto-translate a page into `lang` and save as a DRAFT (not served)."""
    if b.lang not in PHASE_1_LANGS or b.lang == "en":
        raise HTTPException(400, "Unsupported language")
    page = await get_published_page(session, b.slug)
    if not page:
        raise HTTPException(404, "Page not found")
    md = page.get("metadata") or {}
    sub = md.get("subtitle") if isinstance(md, dict) else None
    title_t, sub_t, body_t, provider = await translate_content_page(
        session, b.slug, page["title"], sub, page["body"], b.lang)
    return {"slug": b.slug, "lang": b.lang, "status": "draft", "provider": provider,
            "title": title_t, "subtitle": sub_t, "body": body_t}


@router.put("")
async def save_edit(b: EditBody, session: AsyncSession = Depends(get_db_session_fa)):
    """Save human-edited translation (stays a draft until approved)."""
    packed = (b.title or "") + "\x1f" + (b.subtitle or "")
    res = await session.execute(sql_text(
        "UPDATE page_translations SET translated_title=:t, translated_body=:b, "
        "last_updated=timezone('UTC', now()) "
        "WHERE domain='coin' AND resource_type=:rt AND resource_id=:s AND language_code=:l"
    ), {"t": packed, "b": b.body, "rt": _RT, "s": b.slug, "l": b.lang})
    if res.rowcount == 0:
        # no draft yet — insert one
        await session.execute(sql_text(
            "INSERT INTO page_translations (domain,resource_type,resource_id,language_code,"
            "source_text_hash,source_text,translated_title,translated_body,provider,char_count,reviewed) "
            "VALUES ('coin',:rt,:s,:l,'manual','',:t,:b,'manual',length(:b),false)"
        ), {"rt": _RT, "s": b.slug, "l": b.lang, "t": packed, "b": b.body})
    await session.commit()
    return {"ok": True, "status": "draft"}


@router.post("/approve")
async def approve(b: LangBody, session: AsyncSession = Depends(get_db_session_fa)):
    """Approve a translation — it is now served on the live site and protected
    from being overwritten by the machine (manual_override)."""
    res = await session.execute(sql_text(
        "UPDATE page_translations SET reviewed=true, manual_override=true, "
        "last_updated=timezone('UTC', now()) "
        "WHERE domain='coin' AND resource_type=:rt AND resource_id=:s AND language_code=:l"
    ), {"rt": _RT, "s": b.slug, "l": b.lang})
    await session.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "No translation to approve — generate a draft first")
    return {"ok": True, "status": "approved"}


@router.post("/unapprove")
async def unapprove(b: LangBody, session: AsyncSession = Depends(get_db_session_fa)):
    await session.execute(sql_text(
        "UPDATE page_translations SET reviewed=false "
        "WHERE domain='coin' AND resource_type=:rt AND resource_id=:s AND language_code=:l"
    ), {"rt": _RT, "s": b.slug, "l": b.lang})
    await session.commit()
    return {"ok": True, "status": "draft"}


@router.delete("")
async def delete(slug: str = Query(...), lang: str = Query(...),
                 session: AsyncSession = Depends(get_db_session_fa)):
    await session.execute(sql_text(
        "DELETE FROM page_translations WHERE domain='coin' AND resource_type=:rt "
        "AND resource_id=:s AND language_code=:l"
    ), {"rt": _RT, "s": slug, "l": lang})
    await session.commit()
    return {"ok": True, "status": "none"}
