"""Top-level conftest — stubs tuneapi and other internal deps so the new
src/translation modules can be imported without hitting the real DB or APIs.
"""
import sys, types
from pathlib import Path
from pydantic import BaseModel

# Stub tuneapi
tu_mod = types.ModuleType("tuneapi")
tt_mod = types.ModuleType("tuneapi.tt")
ta_mod = types.ModuleType("tuneapi.ta")
tu_inner = types.ModuleType("tuneapi.tu")
class _Logger:
    def info(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
    def debug(self, *a, **kw): pass
tu_inner.logger = _Logger()
class _SimplerTimes:
    @staticmethod
    def get_now_human(): return "now"
tu_inner.SimplerTimes = _SimplerTimes
class _BM(BaseModel): pass
tt_mod.BM = _BM
def _F(*a, **kw):
    if a: return a[-1] if len(a) > 1 else None
    return kw.get("default")
tt_mod.F = _F
ta_mod.to_openai_chunk = lambda x: x
tu_mod.tt = tt_mod; tu_mod.ta = ta_mod; tu_mod.tu = tu_inner
sys.modules.update({"tuneapi": tu_mod, "tuneapi.tt": tt_mod, "tuneapi.ta": ta_mod, "tuneapi.tu": tu_inner})
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
