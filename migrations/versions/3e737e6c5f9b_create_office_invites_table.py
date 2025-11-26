"""create_office_invites_table

Revision ID: 3e737e6c5f9b
Revises: beee08958782
Create Date: 2025-11-17 22:25:17.345672

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e737e6c5f9b'
down_revision: Union[str, Sequence[str], None] = 'beee08958782'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create office_invites table for invite system."""
    op.create_table(
        'office_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('office_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['office_id'], ['offices.id'], name='fk_office_invites_office_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_office_invites_created_by'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token', name='uq_office_invites_token')
    )
    op.create_index('ix_office_invites_id', 'office_invites', ['id'])
    op.create_index('ix_office_invites_token', 'office_invites', ['token'])
    op.create_index('ix_office_invites_office_id', 'office_invites', ['office_id'])


def downgrade() -> None:
    """Drop office_invites table."""
    op.drop_index('ix_office_invites_office_id', table_name='office_invites')
    op.drop_index('ix_office_invites_token', table_name='office_invites')
    op.drop_index('ix_office_invites_id', table_name='office_invites')
    op.drop_table('office_invites')
