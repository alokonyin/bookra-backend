"""backfill_default_offices_for_existing_operators

Revision ID: cca393e2aef1
Revises: c5026b542f60
Create Date: 2025-11-17 22:24:16.800007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cca393e2aef1'
down_revision: Union[str, Sequence[str], None] = 'c5026b542f60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create default 'Main Office' for each existing operator and assign their trips to it."""
    # This migration is for backfilling existing data only
    # For fresh databases, there's nothing to backfill, so we skip it
    pass


def downgrade() -> None:
    """Remove default offices and unset office_id on trips."""
    pass
