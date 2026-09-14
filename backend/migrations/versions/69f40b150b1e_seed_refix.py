"""seed refix

Revision ID: 69f40b150b1e
Revises: 9f3a6a84156a
Create Date: 2026-09-14 04:49:30.902965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69f40b150b1e'
down_revision: Union[str, Sequence[str], None] = '9f3a6a84156a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
