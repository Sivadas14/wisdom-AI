"""Sarvam-30B AI chat provider.

Used as a *direct* Indic-language chat option (Phase 2 / advanced) — produces
responses natively in the target Indian language without going through
English-translation. Currently $0/token on Sarvam's first-party API.

For PHASE 1, the production code path uses
`src.translation.chat_lang_wrapper.translate_around_chat()` which:
  1. Translates the user's Indic message → English via Sarvam Mayura
  2. Runs the EXISTING RAG-grounded GPT-4o pipeline (preserves citations)
  3. Translates the English response → user's Indic language

That preserves all the Ramana-corpus grounding and citation extraction work
already in chat_completions(). This module is the alternative — call it
directly if you want native Sarvam-30B generation without RAG.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from src.settings import get_settings

log = logging.getLogger("ai.providers")


# ---------------------------------------------------------------------------
# Indic-language system prompts (preserve Sanskrit terms in original script)
# ---------------------------------------------------------------------------

SARVAM_SYSTEM_PROMPTS: dict[str, str] = {
    "hi": (
        "आप 'अरुणाचल समुद्र' हैं — श्री रमण महर्षि के उपदेशों पर आधारित एक चिंतनशील साथी। "
        "केवल हिन्दी में देवनागरी लिपि में उत्तर दें। सरल, आदरयुक्त, आध्यात्मिक भाषा का प्रयोग करें। "
        "संस्कृत मूल शब्दों (आत्मन्, ब्रह्म, मोक्ष, ज्ञान) को अपरिवर्तित रखें। "
        "केवल अधिकृत स्रोतों से उत्तर दें — श्री रमण महर्षि के लेखन और रमणाश्रम के मान्य ग्रंथों से। "
        "किसी अन्य परंपरा या सामान्य ज्ञान का उपयोग न करें।"
    ),
    "ta": (
        "நீங்கள் 'அருணாசல சமுத்திரம்' — ஸ்ரீ ரமண மகரிஷியின் உபதேசங்களை அடிப்படையாகக் கொண்ட "
        "ஒரு சிந்தனைத் துணை. தமிழில் மட்டுமே பதிலளியுங்கள். எளிய, மரியாதையான, "
        "ஆன்மிக மொழியைப் பயன்படுத்துங்கள். சமஸ்கிருத மூலச் சொற்களை (ஆத்மா, பிரம்மம், மோக்ஷம், ஞானம்) "
        "மாற்றாமல் வைத்திருங்கள். ஸ்ரீ ரமண மகரிஷியின் எழுத்துக்களிலிருந்து மட்டுமே பதிலளியுங்கள்."
    ),
    "te": (
        "మీరు 'అరుణాచల సముద్ర' — శ్రీ రమణ మహర్షి బోధనలపై ఆధారపడిన ఒక ధ్యానపూర్వక సహచరుడు. "
        "తెలుగులో మాత్రమే సమాధానం ఇవ్వండి. సరళమైన, గౌరవపూర్వకమైన, ఆధ్యాత్మిక భాషను ఉపయోగించండి. "
        "సంస్కృత మూల పదాలను (ఆత్మ, బ్రహ్మ, మోక్ష, జ్ఞానం) మార్చకండి. "
        "శ్రీ రమణ మహర్షి రచనల నుండి మాత్రమే సమాధానం ఇవ్వండి."
    ),
    "bn": (
        "আপনি 'অরুণাচল সমুদ্র' — শ্রী রমণ মহর্ষির শিক্ষার উপর ভিত্তি করে একটি ধ্যানমগ্ন সঙ্গী। "
        "শুধুমাত্র বাংলায় উত্তর দিন। সরল, শ্রদ্ধাপূর্ণ, আধ্যাত্মিক ভাষা ব্যবহার করুন। "
        "সংস্কৃত মূল শব্দ (আত্মন, ব্রহ্ম, মোক্ষ, জ্ঞান) অপরিবর্তিত রাখুন। "
        "শুধুমাত্র শ্রী রমণ মহর্ষির লেখা থেকে উত্তর দিন।"
    ),
    "ml": (
        "നിങ്ങൾ 'അരുണാചല സമുദ്ര' — ശ്രീ രമണ മഹർഷിയുടെ ഉപദേശങ്ങളെ അടിസ്ഥാനമാക്കിയുള്ള "
        "ഒരു ധ്യാനാത്മക സഹചാരി. മലയാളത്തിൽ മാത്രം ഉത്തരം നൽകുക. ലളിതവും, മാന്യവും, "
        "ആത്മീയവുമായ ഭാഷ ഉപയോഗിക്കുക. സംസ്കൃത മൂല പദങ്ങൾ (ആത്മാവ്, ബ്രഹ്മം, മോക്ഷം, ജ്ഞാനം) "
        "മാറ്റമില്ലാതെ സൂക്ഷിക്കുക. ശ്രീ രമണ മഹർഷിയുടെ കൃതികളിൽ നിന്ന് മാത്രം ഉത്തരം നൽകുക."
    ),
}


# ---------------------------------------------------------------------------
# Sarvam-30B caller
# ---------------------------------------------------------------------------

async def call_sarvam_30b(
    prompt: str,
    lang: str,
    *,
    rag_context: Optional[str] = None,
    temperature: float = 0.6,
    max_tokens: int = 800,
    timeout: float = 30.0,
) -> str:
    """Generate a response in the target Indic language via Sarvam-30B.

    Args:
        prompt:      The user's message (in the target language).
        lang:        Target language code (must be in SARVAM_SYSTEM_PROMPTS).
        rag_context: Optional retrieved Ramana-corpus passages, in the target lang.
                     If None, the model relies on its own training. Recommended:
                     pass at least one passage so responses stay grounded.
        temperature, max_tokens, timeout: standard LLM knobs.

    Returns:
        The assistant's response text.

    Raises:
        ValueError if lang not supported.
        httpx.HTTPError on API failure (caller falls back to OpenAI).
    """
    if lang not in SARVAM_SYSTEM_PROMPTS:
        raise ValueError(f"Sarvam-30B Indic prompt not configured for lang={lang!r}")

    settings = get_settings()
    system_msg = SARVAM_SYSTEM_PROMPTS[lang]
    if rag_context:
        system_msg += "\n\n--- संदर्भ / RELEVANT PASSAGES ---\n" + rag_context

    headers = {
        "api-subscription-key": settings.sarvam_api_key,
        "Content-Type": "application/json",
    }
    body = {
        "model": "sarvam-m",   # Sarvam's chat-tuned model. Verify name at integration time on docs.sarvam.ai
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            "https://api.sarvam.ai/v1/chat/completions",
            headers=headers,
            json=body,
        )
        r.raise_for_status()
        data = r.json()

    # OpenAI-compatible shape: {"choices":[{"message":{"content":"..."}}]}
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        log.error("Unexpected Sarvam-30B response shape: %s", data)
        raise RuntimeError(f"Bad Sarvam-30B response: {e}")
