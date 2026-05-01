"""AI providers — Sarvam-30B for Indic chat, plus the language-aware chat wrapper.

Module layout:
    src/ai/
    ├── __init__.py            (this file)
    └── providers.py           (Sarvam-30B + Indic system prompts)

The chat language wrapper that translates user input → existing RAG → translates
the response back lives in `src.translation.chat_lang_wrapper`.
"""

from src.ai.providers import call_sarvam_30b, SARVAM_SYSTEM_PROMPTS

__all__ = ["call_sarvam_30b", "SARVAM_SYSTEM_PROMPTS"]
