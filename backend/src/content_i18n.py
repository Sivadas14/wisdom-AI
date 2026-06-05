"""
Translate server-rendered content pages — Sarvam-first (your funded provider).

Sarvam translates PLAIN TEXT (Indic), so we translate the text *inside* each HTML
tag and put it back, leaving markup intact. Provider per language:
  - Indic  -> Sarvam (primary), then Google, then Azure
  - Others -> Azure, then Google, then Sarvam
Provider clients are called DIRECTLY (no DB) so text nodes can be translated
concurrently safely; the finished page is cached once per (slug, lang).

Fail-safe: any node that fails keeps its English text; if nothing translates,
the page stays fully English. A page can never break.
"""
from __future__ import annotations

import asyncio
from typing import Optional, Tuple

import lxml.html
from sqlalchemy.ext.asyncio import AsyncSession

from src.translation import PHASE_1_LANGS, INDIC_LANGS, cache
from src.translation.providers import call_sarvam, call_azure, call_google

LANG_DISPLAY = [
    ("en", "English"), ("hi", "हिन्दी"), ("ta", "தமிழ்"), ("te", "తెలుగు"),
    ("bn", "বাংলা"), ("ml", "മലയാളം"), ("es", "Español"), ("fr", "Français"),
    ("de", "Deutsch"), ("nl", "Nederlands"), ("sv", "Svenska"), ("da", "Dansk"),
    ("no", "Norsk"), ("fi", "Suomi"), ("ar", "العربية"), ("zh-CN", "中文"),
]
RTL_LANGS = {"ar"}
_SKIP_TAGS = {"script", "style", "code", "pre"}
_SEM = asyncio.Semaphore(6)


async def _translate_text(text: str, lang: str) -> Tuple[Optional[str], Optional[str]]:
    """Translate one plain-text string via the best available provider. No DB."""
    chain = (["sarvam", "google", "azure"] if lang in INDIC_LANGS
             else ["azure", "google", "sarvam"])
    for prov in chain:
        try:
            if prov == "sarvam":
                out = await call_sarvam(text, lang, "en", timeout=15.0)
            elif prov == "azure":
                out = await call_azure(text, lang, "en", timeout=15.0)
            else:
                out = await call_google(text, lang, "en", timeout=15.0)
            if out and out.strip():
                return out, prov
        except Exception:
            continue
    return None, None


def _inner_html(root) -> str:
    out = root.text or ""
    for child in root:
        out += lxml.html.tostring(child, encoding="unicode")
    return out


async def _translate_html_textnodes(body_html: str, lang: str):
    """Translate text nodes concurrently, preserving tags. Returns (html, provider)."""
    try:
        root = lxml.html.fromstring("<div>" + body_html + "</div>")
    except Exception:
        return None, None

    holders = []
    for el in root.iter():
        tag = el.tag.lower() if isinstance(el.tag, str) else ""
        if tag in _SKIP_TAGS:
            continue
        if el.text and el.text.strip():
            holders.append((el, "text"))
        if el.tail and el.tail.strip():
            holders.append((el, "tail"))
    if not holders:
        return body_html, "noop"

    async def _one(seg: str):
        async with _SEM:
            return await _translate_text(seg.strip(), lang)

    results = await asyncio.gather(*[_one(getattr(el, attr)) for el, attr in holders])

    any_ok = False
    provider = None
    for (el, attr), (translated, prov) in zip(holders, results):
        if not translated:
            continue
        any_ok = True
        provider = provider or prov
        orig = getattr(el, attr)
        lead = orig[: len(orig) - len(orig.lstrip())]
        trail = orig[len(orig.rstrip()):]
        setattr(el, attr, lead + translated.strip() + trail)

    if not any_ok:
        return None, None
    return _inner_html(root), provider


async def translate_content_page(
    session: AsyncSession, slug: str, title: str, body_html: str, lang: str
) -> Tuple[str, str, str]:
    """Return (title, body_html, provider) in `lang`; English on any failure."""
    if lang == "en" or lang not in PHASE_1_LANGS:
        return title, body_html, "source"

    # 1. cache
    try:
        cached = await cache.lookup_by_resource(
            session, domain="coin", resource_type="contentpage",
            resource_id=slug, target_lang=lang,
        )
        if cached and cached.translated_body:
            return (cached.translated_title or title), cached.translated_body, (cached.provider or "cache")
    except Exception:
        pass

    # 2. body (tag-preserving, concurrent, Sarvam-first for Indic)
    body_t, provider = await _translate_html_textnodes(body_html, lang)
    if not body_t:
        return title, body_html, "source"

    # 3. title
    title_t = title
    try:
        t, _ = await _translate_text(title, lang)
        if t and t.strip():
            title_t = t.strip()
    except Exception:
        pass

    # 4. cache
    try:
        await cache.upsert(
            session, domain="coin", resource_type="contentpage", resource_id=slug,
            language_code=lang, source_text=body_html, translated_body=body_t,
            translated_title=title_t, provider=provider or "sarvam", quality_score=0.9,
        )
    except Exception:
        pass

    return title_t, body_t, provider or "sarvam"
