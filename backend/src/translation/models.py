"""SQLAlchemy ORM mirrors for the translation system tables.

Drop-in module — these classes mirror the DDL in
`alembic/versions/2026_05_01_0900_translation_system.py`.

Add to existing src/db.py imports OR import from here directly.

Usage in queries:
    from src.translation.models import Language, PageTranslation
    result = await session.execute(
        select(PageTranslation).where(
            PageTranslation.source_text_hash == hash_,
            PageTranslation.language_code == "hi",
        )
    )
"""
from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Reuse the project's existing Base from src.db
from src.db import Base


class Language(Base):
    """Registry of supported locales."""
    __tablename__ = "languages"

    code:         Mapped[str]  = mapped_column(String(10), primary_key=True)
    name_english: Mapped[str]  = mapped_column(String(100), nullable=False)
    name_native:  Mapped[str]  = mapped_column(String(100), nullable=False)
    rtl:          Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active:    Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    phase:        Mapped[int]  = mapped_column(SmallInteger, nullable=False, default=1)
    sort_order:   Mapped[int]  = mapped_column(SmallInteger, nullable=False, default=100)
    created_at:   Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TranslationProvider(Base):
    """Catalog of translation providers and their cost / free tier metadata."""
    __tablename__ = "translation_providers"

    id:               Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:             Mapped[str]   = mapped_column(String(50), nullable=False, unique=True)
    is_active:        Mapped[bool]  = mapped_column(Boolean, nullable=False, default=True)
    cost_per_million: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    free_tier_chars:  Mapped[int]   = mapped_column(BigInteger, nullable=False, default=0)
    priority:         Mapped[int]   = mapped_column(SmallInteger, nullable=False, default=100)
    config:           Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class PageTranslation(Base):
    """The cache. One row per (domain, resource, language)."""
    __tablename__ = "page_translations"
    __table_args__ = (
        UniqueConstraint("domain", "resource_type", "resource_id", "language_code",
                         name="uq_page_translations_resource_lang"),
        Index("idx_page_trans_lookup", "domain", "resource_id", "language_code"),
        Index("idx_page_trans_hash", "source_text_hash", "language_code"),
    )

    id:               Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                                       server_default=func.gen_random_uuid())
    domain:           Mapped[str]  = mapped_column(String(20), nullable=False, default="coin")
    resource_type:    Mapped[str]  = mapped_column(String(50), nullable=False)
    resource_id:      Mapped[str]  = mapped_column(String(255), nullable=False)
    language_code:    Mapped[str]  = mapped_column(String(10), ForeignKey("languages.code"), nullable=False)
    source_text_hash: Mapped[str]  = mapped_column(CHAR(64), nullable=False)
    source_text:      Mapped[str]  = mapped_column(Text, nullable=False)
    translated_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    translated_body:  Mapped[str]  = mapped_column(Text, nullable=False)
    provider:         Mapped[str]  = mapped_column(String(50), ForeignKey("translation_providers.name"), nullable=False)
    quality_score:    Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    manual_override:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_approved:      Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cached_at:        Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True),
                                                                server_default=func.now(), nullable=False)
    last_updated:     Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True),
                                                                server_default=func.now(), nullable=False)
    char_count:       Mapped[int] = mapped_column(Integer, nullable=False)
    edited_by:        Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)


class AIResponseTranslation(Base):
    """Audit log of every AI chat response per language. Indexed for user/session lookups."""
    __tablename__ = "ai_response_translations"

    id:              Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                                       server_default=func.gen_random_uuid())
    user_id:         Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    session_id:      Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_hash:     Mapped[str] = mapped_column(CHAR(64), nullable=False)
    prompt_text:     Mapped[str] = mapped_column(Text, nullable=False)
    response_text:   Mapped[str] = mapped_column(Text, nullable=False)
    language_code:   Mapped[str] = mapped_column(String(10), ForeignKey("languages.code"), nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(20), nullable=False)  # 'native' | 'translated'
    provider:        Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    char_count:      Mapped[int] = mapped_column(Integer, nullable=False)
    created_at:      Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True),
                                                               server_default=func.now(), nullable=False)


class LanguagePreference(Base):
    """Per-user preferred language. Linked by Supabase user UUID."""
    __tablename__ = "language_preferences"

    user_id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    preferred_language: Mapped[str] = mapped_column(String(10), ForeignKey("languages.code"), nullable=False)
    auto_translate_ai:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_updated:       Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True),
                                                                  server_default=func.now(), nullable=False)


class TranslationUsageDaily(Base):
    """Cost ledger — one row per (date, provider) tuple."""
    __tablename__ = "translation_usage_daily"

    usage_date:    Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    provider:      Mapped[str] = mapped_column(String(50), ForeignKey("translation_providers.name"), primary_key=True)
    chars_used:    Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    api_calls:     Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_estimate: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
