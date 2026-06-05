"""
Translate server-rendered content pages into the site's supported languages.

Reuses the existing translation stack:
  - HTML-safe translation via Azure (textType=html), Google fallback — preserves
    tags, and covers all PHASE_1 languages (incl. Indic) in a single call.
  - Per-(slug, lang) caching via src.translation.cache, so each page+language is
    translated once. Admin/manual overrides in the cache are respected.

Fail-safe: on ANY error, returns the original English title/body, so a content
page never breaks because of translation.
"""
from __future__ import annotations

from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.translation import PHASE_1_LANGS, cache
from src.translation.providers import call_azure, call_google

# Native display names for the language switcher (kept in PHASE_1_LANGS order-ish).
LANG_DISPLAY = [
    ("en", "English"),
    ("hi", "हिन्दी"),
    ("ta", "தமிழ்"),
    ("te", "తెలుగు"),
    ("bn", "বাংলা"),
    ("ml", "മലയാളം"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("nl", "Nederlands"),
    ("sv", "Svenska"),
    ("da", "Dansk"),
    ("no", "Norsk"),
    ("fi", "Suomi"),
    ("ar", "العربية"),
    ("zh-CN", "中文"),
]

RTL_LANGS = {"ar"}


async def _translate_html(text: str, lang: str) -> Tuple[str | None, str | None]:
    """HTML-mode translation: Azure first, Google fallback. Returns (text, provider)."""
    try:
        out = await call_azure(text, lang, "en", timeout=20.0, html=True)
        if out:
            return out, "azure"
    except Exception:
        pass
    try:
        out = await call_google(text, lang, "en", timeout=20.0, html=True)
        if out:
            return out, "google"
    except Exception:
        pass
    return None, None


async def translate_content_page(
    session: AsyncSession, slug: str, title: str, body_html: str, lang: str
) -> Tuple[str, str, str]:
    """Return (title, body_html, provider) in `lang`. Falls back to English on failure."""
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

    # 2. translate body (HTML-safe) + title (plain)
    body_t, provider = await _translate_html(body_html, lang)
    if not body_t:
        return title, body_html, "source"  # graceful — show English

    title_t = title
    try:
        t = await call_azure(title, lang, "en", timeout=10.0)
        if t:
            title_t = t
    except Exception:
        pass

    # 3. cache result (manual overrides are protected inside cache.upsert)
    try:
        await cache.upsert(
            session, domain="coin", resource_type="contentpage", resource_id=slug,
            language_code=lang, source_text=body_html, translated_body=body_t,
            translated_title=title_t, provider=provider or "azure", quality_score=0.9,
        )
    except Exception:
        pass

    return title_t, body_t, provider or "azure"
