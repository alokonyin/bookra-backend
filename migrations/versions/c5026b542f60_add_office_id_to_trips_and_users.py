"""add_office_id_to_trips_and_users

Revision ID: c5026b542f60
Revises: 4fcde71db2cf
Create Date: 2025-11-17 22:23:48.314871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5026b542f60'
down_revision: Union[str, Sequence[str], None] = '4fcde71db2cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add office_id columns to trips and users tables."""
    # Add office_id to trips table (nullable for now)
    op.add_column('trips', sa.Column('office_id', sa.Integer(), nullable=True))
    op.create_index('ix_trips_office_id', 'trips', ['office_id'])
    op.create_foreign_key('fk_trips_office_id', 'trips', 'offices', ['office_id'], ['id'])

    # Add office_id to users table (nullable, for office role users)
    op.add_column('users', sa.Column('office_id', sa.Integer(), nullable=True))
    op.create_index('ix_users_office_id', 'users', ['office_id'])
    op.create_foreign_key('fk_users_office_id', 'users', 'offices', ['office_id'], ['id'])


def downgrade() -> None:
    """Remove office_id columns from trips and users tables."""
    # Drop users office_id
    op.drop_constraint('fk_users_office_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_office_id', table_name='users')
    op.drop_column('users', 'office_id')

    # Drop trips office_id
    op.drop_constraint('fk_trips_office_id', 'trips', type_='foreignkey')
    op.drop_index('ix_trips_office_id', table_name='trips')
    op.drop_column('trips', 'office_id')
