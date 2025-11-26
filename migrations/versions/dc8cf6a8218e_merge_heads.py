"""merge_heads

Revision ID: dc8cf6a8218e
Revises: 174ecee9a97f, 45fce33d37dd
Create Date: 2025-11-25 21:27:59.045624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc8cf6a8218e'
down_revision: Union[str, Sequence[str], None] = ('174ecee9a97f', '45fce33d37dd')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
