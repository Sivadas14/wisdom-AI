"""End-to-end tests for the translation system, with all external providers mocked."""
from __future__ import annotations
import sys, types
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.fixture
def stub_settings(monkeypatch):
    class _S:
        sarvam_api_key = "test_sarvam_key"
        azure_translator_key = "test_azure_key"
        azure_translator_region = "centralindia"
        google_translate_key = "test_google_key"
        translation_daily_sarvam_cap = 100
        translation_daily_azure_cap = 100
        translation_daily_google_cap = 50
    settings = _S()
    monkeypatch.setattr("src.settings.get_settings", lambda: settings)
    return settings


class TestProviders:
    @pytest.mark.asyncio
    async def test_sarvam_translates(self, stub_settings):
        from src.translation.providers import call_sarvam, _sarvam_lang
        assert _sarvam_lang("hi") == "hi-IN"
        assert _sarvam_lang("ta") == "ta-IN"

        fake = MagicMock()
        fake.json.return_value = {"translated_text": "नमस्ते दुनिया"}
        fake.raise_for_status = MagicMock()
        with patch("src.translation.providers.httpx.AsyncClient") as mc:
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=None)
            ctx.post = AsyncMock(return_value=fake)
            mc.return_value = ctx
            result = await call_sarvam("Hello world", "hi")
        assert result == "नमस्ते दुनिया"

    @pytest.mark.asyncio
    async def test_azure_translates(self, stub_settings):
        from src.translation.providers import call_azure
        fake = MagicMock()
        fake.json.return_value = [{"translations": [{"text": "Hola", "to": "es"}]}]
        fake.raise_for_status = MagicMock()
        with patch("src.translation.providers.httpx.AsyncClient") as mc:
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=None)
            ctx.post = AsyncMock(return_value=fake)
            mc.return_value = ctx
            result = await call_azure("Hello", "es")
        assert result == "Hola"

    @pytest.mark.asyncio
    async def test_google_translates(self, stub_settings):
        from src.translation.providers import call_google
        fake = MagicMock()
        fake.json.return_value = {"data": {"translations": [{"translatedText": "Bonjour"}]}}
        fake.raise_for_status = MagicMock()
        with patch("src.translation.providers.httpx.AsyncClient") as mc:
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=None)
            ctx.post = AsyncMock(return_value=fake)
            mc.return_value = ctx
            result = await call_google("Hello", "fr")
        assert result == "Bonjour"

    def test_length_ratio_anomaly(self):
        from src.translation.providers import length_ratio_anomaly
        assert length_ratio_anomaly("hello world", "x")
        assert not length_ratio_anomaly("hello", "नमस्ते")
        assert length_ratio_anomaly("", "abc")


class TestCache:
    def test_hash_normalisation(self):
        from src.translation.cache import hash_source
        assert hash_source("hello") == hash_source("  hello  ")
        assert hash_source("Hello") != hash_source("hello")
        assert len(hash_source("x")) == 64


class TestRouting:
    def test_indic_to_sarvam(self):
        from src.translation.gateway import _primary_provider
        for lang in ["hi", "ta", "te", "bn", "ml", "kn", "mr", "gu"]:
            assert _primary_provider(lang) == "sarvam"

    def test_intl_to_azure(self):
        from src.translation.gateway import _primary_provider
        for lang in ["es", "fr", "ar", "de", "ja", "zh-CN"]:
            assert _primary_provider(lang) == "azure"


class TestAIProviders:
    def test_indic_prompts_preserve_sanskrit(self):
        from src.ai.providers import SARVAM_SYSTEM_PROMPTS
        assert "आत्मन्" in SARVAM_SYSTEM_PROMPTS["hi"]
        assert "ब्रह्म" in SARVAM_SYSTEM_PROMPTS["hi"]
        assert "ஆத்மா" in SARVAM_SYSTEM_PROMPTS["ta"]
        for lang, prompt in SARVAM_SYSTEM_PROMPTS.items():
            assert any(r in prompt for r in ["रमण", "ரமண", "రమణ", "রমণ", "രമണ"]), \
                f"{lang} prompt must reference Ramana"

    @pytest.mark.asyncio
    async def test_unsupported_lang_raises(self, stub_settings):
        from src.ai.providers import call_sarvam_30b
        with pytest.raises(ValueError, match="not configured"):
            await call_sarvam_30b("test", "fr")
