"""Stub: add_email_password_auth — applied to prod from a non-committed branch.

Revision ID: add_email_password_auth
Revises: 863df6d72f57
Create Date: 2026-XX-XX

Placeholder so alembic chain resolves. The actual schema change was
applied directly to production without committing the migration file.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'add_email_password_auth'
down_revision: Union[str, Sequence[str], None] = '863df6d72f57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """No-op — change already in production."""
    pass

def downgrade() -> None:
    """Cannot reverse — original migration not preserved in repo."""
    pass
