"""add stimulus jenis spesifikasi

Revision ID: a7b1c9d4e2f0
Revises: 0d3e13679f93
Create Date: 2026-11-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a7b1c9d4e2f0'
down_revision: Union[str, Sequence[str], None] = '0d3e13679f93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('soal_stimulus', sa.Column('jenis', sa.Text(), server_default='teks', nullable=False))
    op.add_column('soal_stimulus', sa.Column('spesifikasi', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('soal_stimulus', 'spesifikasi')
    op.drop_column('soal_stimulus', 'jenis')
