"""
Translate server-rendered content pages — Sarvam-first, PARAGRAPH-level.

Each block (paragraph/heading/list-item/quote) is translated as ONE unit:
  - full-sentence context -> clean output, no fragment artifacts
  - far fewer calls than per-fragment, and concurrency is capped so we don't
    trip Sarvam's rate limit
  - per-block fallback: a block that fails keeps its English text, so a page
    never reverts entirely to English just because one call failed
Provider per language: Indic -> Sarvam (then Google/Azure); others -> Azure
(then Google/Sarvam). Results cached per (slug, lang).
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
_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote",
               "figcaption", "dd", "dt", "td", "th"}
_SEM = asyncio.Semaphore(4)   # gentle on Sarvam's rate limit


async def _translate_text(text: str, lang: str) -> Tuple[Optional[str], Optional[str]]:
    """Translate one plain-text string via the best provider for `lang`. No DB."""
    if not text or not text.strip():
        return text, "noop"
    chain = (["sarvam", "google", "azure"] if lang in INDIC_LANGS
             else ["azure", "google", "sarvam"])
    for prov in chain:
        try:
            if prov == "sarvam":
                out = await call_sarvam(text, lang, "en", timeout=20.0)
            elif prov == "azure":
                out = await call_azure(text, lang, "en", timeout=20.0)
            else:
                out = await call_google(text, lang, "en", timeout=20.0)
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


def _leaf_blocks(root):
    """Block elements that contain text and no nested block elements."""
    blocks = []
    for el in root.iter():
        if not isinstance(el.tag, str) or el.tag not in _BLOCK_TAGS:
            continue
        if any(isinstance(d.tag, str) and d.tag in _BLOCK_TAGS for d in el.iterdescendants()):
            continue  # container block — its children are the real leaves
        txt = el.text_content().strip()
        if txt:
            blocks.append((el, txt))
    return blocks


async def _translate_html_blocks(body_html: str, lang: str):
    """Translate each leaf block; preserve block structure. Returns (html, provider)."""
    try:
        root = lxml.html.fromstring("<div>" + body_html + "</div>")
    except Exception:
        return None, None

    blocks = _leaf_blocks(root)
    if not blocks:
        return body_html, "noop"

    async def _one(text: str):
        async with _SEM:
            return await _translate_text(text, lang)

    results = await asyncio.gather(*[_one(t) for _, t in blocks])

    any_ok = False
    provider = None
    for (el, _txt), (translated, prov) in zip(blocks, results):
        if not translated or not translated.strip():
            continue  # keep this block's English text
        any_ok = True
        provider = provider or prov
        for child in list(el):
            el.remove(child)
        el.text = translated.strip()

    if not any_ok:
        return None, None
    return _inner_html(root), (provider or "sarvam")


async def translate_content_page(
    session: AsyncSession, slug: str, title: str, subtitle: Optional[str],
    body_html: str, lang: str,
) -> Tuple[str, Optional[str], str, str]:
    """Return (title, subtitle, body_html, provider) in `lang`; English on failure."""
    if lang == "en" or lang not in PHASE_1_LANGS:
        return title, subtitle, body_html, "source"

    # 1. cache
    try:
        cached = await cache.lookup_by_resource(
            session, domain="coin", resource_type="contentpage",
            resource_id=slug, target_lang=lang,
        )
        if cached and cached.translated_body:
            _ct = cached.translated_title or ""
            if "\x1f" in _ct:
                _t_part, _s_part = _ct.split("\x1f", 1)
            else:
                _t_part, _s_part = (_ct or title), subtitle
            return (_t_part or title), (_s_part or subtitle), cached.translated_body, (cached.provider or "cache")
    except Exception:
        pass

    # 2. body (paragraph-level, capped concurrency, per-block fallback)
    body_t, provider = await _translate_html_blocks(body_html, lang)
    if not body_t:
        return title, subtitle, body_html, "source"

    # 3. title + subtitle (short, run together)
    title_t = title
    subtitle_t = subtitle
    try:
        tt, _ = await _translate_text(title, lang)
        if tt and tt.strip():
            title_t = tt.strip()
    except Exception:
        pass
    if subtitle:
        try:
            st, _ = await _translate_text(subtitle, lang)
            if st and st.strip():
                subtitle_t = st.strip()
        except Exception:
            pass

    # 4. cache (store translated subtitle in metadata for reuse)
    try:
        await cache.upsert(
            session, domain="coin", resource_type="contentpage", resource_id=slug,
            language_code=lang, source_text=body_html, translated_body=body_t,
            translated_title=(title_t + "\x1f" + (subtitle_t or "")),
            provider=provider or "sarvam", quality_score=0.9,
        )
    except Exception:
        pass

    return title_t, subtitle_t, body_t, provider or "sarvam"
