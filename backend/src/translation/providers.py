"""Translation provider clients — pure functions, no caching, no failover.

The gateway in `gateway.py` composes these into the actual translate-with-failover
pipeline. Keeping this module narrow means the providers are easy to mock in tests.

Three providers:
  • Sarvam Mayura — PRIMARY for Indic languages (best quality on Indian content)
  • Azure Translator — PRIMARY for international, SECONDARY fallback for Indic
  • Google Translate — TERTIARY fallback (only called if both Sarvam + Azure fail)

All clients are async (httpx.AsyncClient) and read keys from src.settings.Settings.
"""
from __future__ import annotations

import httpx
from tuneapi import tu

from src.settings import get_settings


# ---------------------------------------------------------------------------
# Sarvam Mayura
# ---------------------------------------------------------------------------

# Sarvam uses BCP-47 codes with -IN region suffix for Indian languages.
_SARVAM_LANG_MAP = {
    "hi": "hi-IN", "ta": "ta-IN", "te": "te-IN", "bn": "bn-IN", "ml": "ml-IN",
    "kn": "kn-IN", "mr": "mr-IN", "gu": "gu-IN", "pa": "pa-IN", "or": "od-IN",
    "ur": "ur-IN", "en": "en-IN",
}


def _sarvam_lang(code: str) -> str:
    return _SARVAM_LANG_MAP.get(code, code)


async def call_sarvam(text: str, target: str, source: str = "en", timeout: float = 10.0) -> str:
    """Translate via Sarvam Mayura.

    Raises httpx.HTTPError on network/HTTP failures — caller handles failover.
    """
    settings = get_settings()
    headers = {
        "api-subscription-key": settings.sarvam_api_key,
        "Content-Type": "application/json",
    }
    body = {
        "input": text,
        "source_language_code": _sarvam_lang(source),
        "target_language_code": _sarvam_lang(target),
        "speaker_gender": "Female",
        "mode": "formal",
        "model": "mayura:v1",
        "enable_preprocessing": True,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            "https://api.sarvam.ai/translate",
            headers=headers,
            json=body,
        )
        r.raise_for_status()
        data = r.json()
    return data.get("translated_text", "") or ""


# ---------------------------------------------------------------------------
# Azure Translator
# ---------------------------------------------------------------------------

async def call_azure(text: str, target: str, source: str = "en", timeout: float = 10.0) -> str:
    """Translate via Microsoft Azure Cognitive Translator (v3 API).

    2 million characters per month FREE forever — preferred fallback / international primary.
    """
    settings = get_settings()
    headers = {
        "Ocp-Apim-Subscription-Key":    settings.azure_translator_key,
        "Ocp-Apim-Subscription-Region": settings.azure_translator_region,
        "Content-Type":                 "application/json",
    }
    params = {"api-version": "3.0", "from": source, "to": target}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            "https://api.cognitive.microsofttranslator.com/translate",
            params=params,
            headers=headers,
            json=[{"Text": text}],
        )
        r.raise_for_status()
        data = r.json()
    # Azure returns: [{"translations":[{"text":"...","to":"hi"}]}]
    if data and isinstance(data, list) and data[0].get("translations"):
        return data[0]["translations"][0].get("text", "") or ""
    return ""


# ---------------------------------------------------------------------------
# Google Translate (tertiary fallback)
# ---------------------------------------------------------------------------

async def call_google(text: str, target: str, source: str = "en", timeout: float = 10.0) -> str:
    """Translate via Google Cloud Translation v2.

    Only called if both Sarvam and Azure fail. 500K chars/month free.
    """
    settings = get_settings()
    if not settings.google_translate_key:
        raise RuntimeError("GOOGLE_TRANSLATE_KEY not configured; cannot use Google fallback")

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            "https://translation.googleapis.com/language/translate/v2",
            params={"key": settings.google_translate_key},
            json={"q": text, "source": source, "target": target, "format": "text"},
        )
        r.raise_for_status()
        data = r.json()
    return data["data"]["translations"][0].get("translatedText", "") or ""


# ---------------------------------------------------------------------------
# Quality heuristic
# ---------------------------------------------------------------------------

def length_ratio_anomaly(src: str, tgt: str) -> bool:
    """Detect extreme length-ratio outliers that often indicate provider failure.

    A translation that's <30% or >400% the source length is suspect.
    Returns True if anomaly detected (caller should flag quality_score=0.7).
    """
    if not src or not tgt:
        return True
    ratio = len(tgt) / len(src)
    return ratio < 0.3 or ratio > 4.0
