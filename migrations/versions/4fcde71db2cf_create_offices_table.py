"""create_offices_table

Revision ID: 4fcde71db2cf
Revises: ee7d1f8dd8d9
Create Date: 2025-11-17 22:21:33.521703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4fcde71db2cf'
down_revision: Union[str, Sequence[str], None] = 'ee7d1f8dd8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create offices table."""
    op.create_table(
        'offices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=False),
        sa.Column('office_name', sa.String(), nullable=False),
        sa.Column('city', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['operator_id'], ['users.id'], name='fk_offices_operator_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_offices_email')
    )
    op.create_index('ix_offices_id', 'offices', ['id'])
    op.create_index('ix_offices_operator_id', 'offices', ['operator_id'])
    op.create_index('ix_offices_email', 'offices', ['email'])


def downgrade() -> None:
    """Drop offices table."""
    op.drop_index('ix_offices_email', table_name='offices')
    op.drop_index('ix_offices_operator_id', table_name='offices')
    op.drop_index('ix_offices_id', table_name='offices')
    op.drop_table('offices')
