"""add_company_name_to_users

Revision ID: 45fce33d37dd
Revises: cca393e2aef1
Create Date: 2025-11-25 21:27:25.260433

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45fce33d37dd'
down_revision: Union[str, Sequence[str], None] = 'cca393e2aef1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add company_name column to users table"""
    op.add_column('users', sa.Column('company_name', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove company_name column from users table"""
    op.drop_column('users', 'company_name')
