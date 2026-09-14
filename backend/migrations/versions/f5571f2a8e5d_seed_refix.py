"""seed refix

Revision ID: f5571f2a8e5d
Revises: 33031361f3ba
Create Date: 2026-09-14 04:41:01.592565

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5571f2a8e5d'
down_revision: Union[str, Sequence[str], None] = '33031361f3ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
