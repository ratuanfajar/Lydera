"""seed refix

Revision ID: 9f3a6a84156a
Revises: f5571f2a8e5d
Create Date: 2026-09-14 04:42:22.663256

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f3a6a84156a'
down_revision: Union[str, Sequence[str], None] = 'f5571f2a8e5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
