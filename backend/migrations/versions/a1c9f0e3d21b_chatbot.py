"""chatbot: pgvector extension + block_embeddings, chapter_kb, chat_sessions, chat_messages

Revision ID: a1c9f0e3d21b
Revises: 33031361f3ba
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = 'a1c9f0e3d21b'
down_revision: Union[str, Sequence[str], None] = '33031361f3ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = settings.EMBEDDING_DIM


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'chapter_kb',
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('kb_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('chapter_id'),
    )

    op.create_table(
        'block_embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('block_ids', sa.ARRAY(sa.Integer()), nullable=False),
        sa.Column('heading', sa.Text(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(EMBEDDING_DIM), nullable=False),
        sa.Column('kb_version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_block_embeddings_chapter', 'block_embeddings', ['chapter_id', 'kb_version'])
    # Sengaja TIDAK dibuatkan index HNSW/IVFFlat pada `embedding`. pgvector membatasi index ANN
    # (HNSW maupun IVFFlat) pada tipe `vector` maksimal 2000 dimensi -- text-embedding-3-large
    # (EMBEDDING_MODEL saat ini) keluaran 3072 dimensi, melebihi batas itu. Untuk skala satu
    # classroom (puluhan-ratusan chunk per bab x beberapa bab), brute-force exact scan (dibantu
    # index btree di atas untuk filter awal) masih cukup cepat tanpa ANN index -- kalau nanti
    # volume per classroom jadi sangat besar, pertimbangkan halfvec (batas index 4000 dimensi).

    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('classroom_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['classroom_id'], ['classrooms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_sessions_student_classroom', 'chat_sessions', ['student_id', 'classroom_id'])

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tool_calls', postgresql.JSONB(), nullable=True),
        sa.Column('citations', postgresql.JSONB(), nullable=True),
        sa.Column('scope_klass', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('user', 'assistant')", name='check_chat_message_role'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_session', 'chat_messages', ['session_id', 'id'])


def downgrade() -> None:
    op.drop_index('ix_chat_messages_session', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index('ix_chat_sessions_student_classroom', table_name='chat_sessions')
    op.drop_table('chat_sessions')
    op.drop_index('ix_block_embeddings_chapter', table_name='block_embeddings')
    op.drop_table('block_embeddings')
    op.drop_table('chapter_kb')
    op.execute('DROP EXTENSION IF EXISTS vector')
