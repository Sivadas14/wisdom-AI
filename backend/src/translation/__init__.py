"""Translation system module — adds multilingual support for static page content
and dispatches AI chat to language-appropriate providers.

Module layout:
    src/translation/
    ├── __init__.py            (this file — exposes routers + constants)
    ├── gateway.py             (POST /api/translate)
    ├── providers.py           (Sarvam Mayura + Azure + Google clients)
    ├── page_resolver.py       (GET /api/page/{slug}?lang=xx)
    └── models.py              (SQLAlchemy ORM rows for translation tables)

Apply alongside `src/ai/providers.py` which adds Sarvam-30B for Indic chat.
"""

INDIC_LANGS = {"hi", "ta", "te", "bn", "ml", "kn", "mr", "gu", "pa", "or", "ur"}
PHASE_1_LANGS = {"en", "hi", "ta", "te", "bn", "ml", "es", "fr", "ar"}

from src.translation.gateway import router as translation_router
from src.translation.page_resolver import router as page_router

__all__ = ["translation_router", "page_router", "INDIC_LANGS", "PHASE_1_LANGS"]
