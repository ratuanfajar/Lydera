"""tambah content markup chat messages

Revision ID: 0d3e13679f93
Revises: c3d97c01e878
Create Date: 2026-10-28 07:44:21.585654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0d3e13679f93'
down_revision: Union[str, Sequence[str], None] = 'c3d97c01e878'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chat_messages', sa.Column('content_markup', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('chat_messages', 'content_markup')
