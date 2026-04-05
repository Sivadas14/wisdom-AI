"""add_email_password_auth

Revision ID: add_email_password_auth
Revises: bf454a893619
Create Date: 2025-08-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_email_password_auth'
down_revision: Union[str, Sequence[str], None] = 'bf454a893619'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists (idempotency guard)."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def _constraint_exists(constraint: str) -> bool:
    """Check if a named constraint already exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = :n"
        ),
        {"n": constraint},
    )
    return result.fetchone() is not None


def _index_exists(index: str) -> bool:
    """Check if a named index already exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :n"
        ),
        {"n": index},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    """Add email and password_hash columns; make phone_number nullable.

    All operations are idempotent — safe to re-run if a previous attempt
    failed partway through.
    """
    # --- email column ---
    if not _column_exists('user_profiles', 'email'):
        op.add_column('user_profiles', sa.Column('email', sa.String(), nullable=True))

    if not _constraint_exists('uq_user_profile_email'):
        op.create_unique_constraint('uq_user_profile_email', 'user_profiles', ['email'])

    if not _index_exists('idx_user_profile_email'):
        op.create_index('idx_user_profile_email', 'user_profiles', ['email'])

    # --- password_hash column ---
    if not _column_exists('user_profiles', 'password_hash'):
        op.add_column('user_profiles', sa.Column('password_hash', sa.String(), nullable=True))

    # --- make phone_number nullable (safe to run even if already nullable) ---
    op.alter_column(
        'user_profiles',
        'phone_number',
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    """Remove email and password_hash columns; restore phone_number NOT NULL."""
    op.drop_index('idx_user_profile_email', table_name='user_profiles')
    op.drop_constraint('uq_user_profile_email', 'user_profiles', type_='unique')
    op.drop_column('user_profiles', 'email')
    op.drop_column('user_profiles', 'password_hash')

    # Restore phone_number NOT NULL (only safe if all rows have a value)
    op.alter_column(
        'user_profiles',
        'phone_number',
        existing_type=sa.String(),
        nullable=False,
    )
