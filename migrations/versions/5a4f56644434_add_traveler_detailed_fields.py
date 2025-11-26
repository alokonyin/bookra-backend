"""add_traveler_detailed_fields

Revision ID: 5a4f56644434
Revises: fb8913fb2880
Create Date: 2025-11-17 14:13:18.891326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a4f56644434'
down_revision: Union[str, Sequence[str], None] = 'fb8913fb2880'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add traveler-specific fields to users table
    op.add_column('users', sa.Column('title', sa.String(), nullable=True))
    op.add_column('users', sa.Column('first_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('middle_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('users', sa.Column('nationality', sa.String(), nullable=True))
    op.add_column('users', sa.Column('document_type', sa.String(), nullable=True))
    op.add_column('users', sa.Column('document_number', sa.String(), nullable=True))
    op.add_column('users', sa.Column('address', sa.String(), nullable=True))
    op.add_column('users', sa.Column('city', sa.String(), nullable=True))
    op.add_column('users', sa.Column('country', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove traveler-specific fields from users table
    op.drop_column('users', 'country')
    op.drop_column('users', 'city')
    op.drop_column('users', 'address')
    op.drop_column('users', 'document_number')
    op.drop_column('users', 'document_type')
    op.drop_column('users', 'nationality')
    op.drop_column('users', 'date_of_birth')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'middle_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'title')
