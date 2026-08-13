"""Top-level conftest — stubs heavy internal deps so translation modules can be
imported in tests without hitting the real DB or APIs.

tuneapi has been removed: the project now uses src.llm_shim directly.
"""
import sys, types
from pathlib import Path
from pydantic import BaseModel

sys.modules["polar_sdk"] = types.ModuleType("polar_sdk")
sys.modules["polar_sdk"].Polar = object

import src as _src_pkg  # noqa
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
class StubBase(AsyncAttrs, DeclarativeBase): pass
db_stub = types.ModuleType("src.db")
db_stub.Base = StubBase
async def _gs(): yield None
db_stub.get_db_session_fa = _gs
sys.modules["src.db"] = db_stub
_src_pkg.db = db_stub

class _Settings:
    db_url = "postgresql+asyncpg://x:y@localhost/z"
    sarvam_api_key = "test"
    azure_translator_key = "test"
    azure_translator_region = "centralindia"
    google_translate_key = "test"
    translation_daily_sarvam_cap = 100
    translation_daily_azure_cap = 100
    translation_daily_google_cap = 50
settings_stub = types.ModuleType("src.settings")
settings_stub.Settings = _Settings
settings_stub.get_settings = lambda: _Settings()
settings_stub.get_supabase_client = lambda: None
sys.modules["src.settings"] = settings_stub
_src_pkg.settings = settings_stub

wire_stub = types.ModuleType("src.wire")
class _SR(BaseModel):
    success: bool = True
    message: str | None = None
    data: dict | None = None
wire_stub.SuccessResponse = _SR
sys.modules["src.wire"] = wire_stub
_src_pkg.wire = wire_stub
