"""add table ringkasan and tabel

Revision ID: 22ed630f2f6c
Revises: c4fff23c38ea
Create Date: 2026-10-27 23:43:54.295619

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '22ed630f2f6c'
down_revision: Union[str, Sequence[str], None] = 'c4fff23c38ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('blocks', sa.Column('ringkasan', sa.Text(), nullable=True))
    op.add_column('blocks', sa.Column('tabel', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True))
    op.add_column('soal_stimulus', sa.Column('ringkasan', sa.Text(), nullable=True))
    op.add_column('soal_stimulus', sa.Column('tabel', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('soal_stimulus', 'tabel')
    op.drop_column('soal_stimulus', 'ringkasan')
    op.drop_column('blocks', 'tabel')
    op.drop_column('blocks', 'ringkasan')
