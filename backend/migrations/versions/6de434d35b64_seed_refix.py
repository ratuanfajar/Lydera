"""seed refix

Revision ID: 6de434d35b64
Revises: 69f40b150b1e
Create Date: 2026-09-14 04:49:45.836644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6de434d35b64'
down_revision: Union[str, Sequence[str], None] = '69f40b150b1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
