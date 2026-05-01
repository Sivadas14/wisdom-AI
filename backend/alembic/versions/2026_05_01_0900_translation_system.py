"""Add translation system tables (languages, providers, page_translations,
ai_response_translations, language_preferences, translation_usage_daily) and RLS

Revision ID: 4a8c7e2f9b13
Revises: 863df6d72f57
Create Date: 2026-05-01 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4a8c7e2f9b13'
down_revision: Union[str, Sequence[str], None] = '863df6d72f57'   # <-- previous head; verify with `alembic heads`
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. languages registry --------------------------------------------------
    op.create_table(
        'languages',
        sa.Column('code',         sa.String(length=10), nullable=False),
        sa.Column('name_english', sa.String(length=100), nullable=False),
        sa.Column('name_native',  sa.String(length=100), nullable=False),
        sa.Column('rtl',          sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_active',    sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('phase',        sa.SmallInteger(), nullable=False, server_default=sa.text('1')),
        sa.Column('sort_order',   sa.SmallInteger(), nullable=False, server_default=sa.text('100')),
        sa.Column('created_at',   sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('code'),
    )

    # Phase-1 seed
    op.bulk_insert(
        sa.table('languages',
                 sa.column('code', sa.String),
                 sa.column('name_english', sa.String),
                 sa.column('name_native', sa.String),
                 sa.column('rtl', sa.Boolean),
                 sa.column('phase', sa.SmallInteger),
                 sa.column('sort_order', sa.SmallInteger)),
        [
            {'code': 'en', 'name_english': 'English',   'name_native': 'English',   'rtl': False, 'phase': 1, 'sort_order': 1},
            {'code': 'hi', 'name_english': 'Hindi',     'name_native': 'हिन्दी',     'rtl': False, 'phase': 1, 'sort_order': 2},
            {'code': 'ta', 'name_english': 'Tamil',     'name_native': 'தமிழ்',     'rtl': False, 'phase': 1, 'sort_order': 3},
            {'code': 'te', 'name_english': 'Telugu',    'name_native': 'తెలుగు',    'rtl': False, 'phase': 1, 'sort_order': 4},
            {'code': 'bn', 'name_english': 'Bengali',   'name_native': 'বাংলা',      'rtl': False, 'phase': 1, 'sort_order': 5},
            {'code': 'ml', 'name_english': 'Malayalam', 'name_native': 'മലയാളം',   'rtl': False, 'phase': 1, 'sort_order': 6},
            {'code': 'es', 'name_english': 'Spanish',   'name_native': 'Español',  'rtl': False, 'phase': 1, 'sort_order': 7},
            {'code': 'fr', 'name_english': 'French',    'name_native': 'Français', 'rtl': False, 'phase': 1, 'sort_order': 8},
            {'code': 'ar', 'name_english': 'Arabic',    'name_native': 'العربية',    'rtl': True,  'phase': 1, 'sort_order': 9},
        ],
    )

    # 2. translation_providers registry --------------------------------------
    op.create_table(
        'translation_providers',
        sa.Column('id',               sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name',             sa.String(length=50), nullable=False),
        sa.Column('is_active',        sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('cost_per_million', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('free_tier_chars',  sa.BigInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column('priority',         sa.SmallInteger(), nullable=False, server_default=sa.text('100')),
        sa.Column('config',           postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    op.bulk_insert(
        sa.table('translation_providers',
                 sa.column('name', sa.String),
                 sa.column('cost_per_million', sa.Float),
                 sa.column('free_tier_chars', sa.BigInteger),
                 sa.column('priority', sa.SmallInteger)),
        [
            {'name': 'sarvam',  'cost_per_million': 24.0, 'free_tier_chars': 500_000,   'priority': 1},
            {'name': 'azure',   'cost_per_million': 10.0, 'free_tier_chars': 2_000_000, 'priority': 2},
            {'name': 'google',  'cost_per_million': 20.0, 'free_tier_chars': 500_000,   'priority': 3},
            {'name': 'openai',  'cost_per_million': 12.0, 'free_tier_chars': 0,         'priority': 4},
            {'name': 'manual',  'cost_per_million': 0.0,  'free_tier_chars': 0,         'priority': 0},
        ],
    )

    # 3. page_translations (the cache) ----------------------------------------
    op.create_table(
        'page_translations',
        sa.Column('id',                postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('domain',            sa.String(length=20), nullable=False, server_default=sa.text("'coin'")),
        sa.Column('resource_type',     sa.String(length=50), nullable=False),
        sa.Column('resource_id',       sa.String(length=255), nullable=False),
        sa.Column('language_code',     sa.String(length=10), nullable=False),
        sa.Column('source_text_hash',  sa.CHAR(length=64), nullable=False),
        sa.Column('source_text',       sa.Text(), nullable=False),
        sa.Column('translated_title',  sa.Text(), nullable=True),
        sa.Column('translated_body',   sa.Text(), nullable=False),
        sa.Column('provider',          sa.String(length=50), nullable=False),
        sa.Column('quality_score',     sa.Float(), nullable=True),
        sa.Column('manual_override',   sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_approved',       sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('cached_at',         sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_updated',      sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('char_count',        sa.Integer(), nullable=False),
        sa.Column('edited_by',         postgresql.UUID(as_uuid=True), nullable=True),  # FK to auth.users(id) — not enforced (different schema)
        sa.ForeignKeyConstraint(['language_code'], ['languages.code']),
        sa.ForeignKeyConstraint(['provider'], ['translation_providers.name']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain', 'resource_type', 'resource_id', 'language_code',
                            name='uq_page_translations_resource_lang'),
    )
    op.create_index('idx_page_trans_lookup', 'page_translations',
                    ['domain', 'resource_id', 'language_code'])
    op.create_index('idx_page_trans_hash', 'page_translations',
                    ['source_text_hash', 'language_code'])

    # 4. ai_response_translations (audit log) ---------------------------------
    op.create_table(
        'ai_response_translations',
        sa.Column('id',              postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id',         postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id',      sa.String(length=100), nullable=False),
        sa.Column('prompt_hash',     sa.CHAR(length=64), nullable=False),
        sa.Column('prompt_text',     sa.Text(), nullable=False),
        sa.Column('response_text',   sa.Text(), nullable=False),
        sa.Column('language_code',   sa.String(length=10), nullable=False),
        sa.Column('generation_mode', sa.String(length=20), nullable=False),  # 'native' | 'translated'
        sa.Column('provider',        sa.String(length=50), nullable=True),
        sa.Column('char_count',      sa.Integer(), nullable=False),
        sa.Column('created_at',      sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['language_code'], ['languages.code']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_ai_trans_user_session', 'ai_response_translations',
                    ['user_id', 'session_id', sa.text('created_at DESC')])

    # 5. language_preferences -------------------------------------------------
    op.create_table(
        'language_preferences',
        sa.Column('user_id',            postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('preferred_language', sa.String(length=10), nullable=False),
        sa.Column('auto_translate_ai',  sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_updated',       sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['preferred_language'], ['languages.code']),
        sa.PrimaryKeyConstraint('user_id'),
    )

    # 6. translation_usage_daily (cost ledger) --------------------------------
    op.create_table(
        'translation_usage_daily',
        sa.Column('usage_date',    sa.Date(), nullable=False),
        sa.Column('provider',      sa.String(length=50), nullable=False),
        sa.Column('chars_used',    sa.BigInteger(), nullable=False, server_default=sa.text('0')),
        sa.Column('api_calls',     sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('cost_estimate', sa.Numeric(precision=10, scale=4), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['provider'], ['translation_providers.name']),
        sa.PrimaryKeyConstraint('usage_date', 'provider'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('translation_usage_daily')
    op.drop_table('language_preferences')
    op.drop_index('idx_ai_trans_user_session', table_name='ai_response_translations')
    op.drop_table('ai_response_translations')
    op.drop_index('idx_page_trans_hash', table_name='page_translations')
    op.drop_index('idx_page_trans_lookup', table_name='page_translations')
    op.drop_table('page_translations')
    op.drop_table('translation_providers')
    op.drop_table('languages')
