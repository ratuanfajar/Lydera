"""add evaluaizer justification points

Revision ID: 3283e5f17bcf
Revises: 22ed630f2f6c
Create Date: 2026-10-28 01:32:44.302631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3283e5f17bcf'
down_revision: Union[str, Sequence[str], None] = '22ed630f2f6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('soal_jawaban', sa.Column('error_type', sa.Text(), nullable=True))
    op.add_column('soal_jawaban', sa.Column('justification_points', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True))
    op.add_column('soal_jawaban', sa.Column('needs_review', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('soal_jawaban', 'needs_review')
    op.drop_column('soal_jawaban', 'justification_points')
    op.drop_column('soal_jawaban', 'error_type')
