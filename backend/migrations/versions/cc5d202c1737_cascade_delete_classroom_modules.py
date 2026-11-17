"""cascade delete classroom modules

Revision ID: cc5d202c1737
Revises: 9c1a19fbb3d2
Create Date: 2026-11-17 09:59:29.550070

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cc5d202c1737'
down_revision: Union[str, Sequence[str], None] = '9c1a19fbb3d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _classroom_fk_name() -> str | None:
    return op.get_bind().execute(
        sa.text(
            """
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_attribute a
              ON a.attrelid = c.conrelid
             AND a.attnum = ANY (c.conkey)
            WHERE c.conrelid = 'modules'::regclass
              AND c.contype = 'f'
              AND a.attname = 'classroom_id'
            """
        )
    ).scalar()


def upgrade() -> None:
    """Upgrade schema."""
    name = _classroom_fk_name()
    if name:
        op.drop_constraint(name, 'modules', type_='foreignkey')
    op.create_foreign_key(
        'modules_classroom_id_fkey',
        'modules',
        'classrooms',
        ['classroom_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Downgrade schema."""
    name = _classroom_fk_name()
    if name:
        op.drop_constraint(name, 'modules', type_='foreignkey')
    op.create_foreign_key(
        'modules_classroom_id_fkey',
        'modules',
        'classrooms',
        ['classroom_id'],
        ['id'],
    )
