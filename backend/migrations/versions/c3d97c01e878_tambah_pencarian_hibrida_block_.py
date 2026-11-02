"""tambah pencarian hibrida block embeddings

Revision ID: c3d97c01e878
Revises: cb1cb0782cef
Create Date: 2026-10-28 04:18:54.219199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3d97c01e878'
down_revision: Union[str, Sequence[str], None] = 'cb1cb0782cef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('block_embeddings', sa.Column('lexical_tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('simple', chunk_text)", persisted=True), nullable=True))
    op.add_column('block_embeddings', sa.Column('formula_norm', sa.Text(), server_default='', nullable=False))
    op.create_index('ix_block_embeddings_lexical', 'block_embeddings', ['lexical_tsv'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    op.drop_index('ix_block_embeddings_lexical', table_name='block_embeddings', postgresql_using='gin')
    op.drop_column('block_embeddings', 'formula_norm')
    op.drop_column('block_embeddings', 'lexical_tsv')
