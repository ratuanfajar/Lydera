"""tambah review started at

Revision ID: cb1cb0782cef
Revises: 3283e5f17bcf
Create Date: 2026-10-28 03:34:38.177424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cb1cb0782cef'
down_revision: Union[str, Sequence[str], None] = '3283e5f17bcf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('quiz_progress', sa.Column('review_started_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('quiz_progress', 'review_started_at')
