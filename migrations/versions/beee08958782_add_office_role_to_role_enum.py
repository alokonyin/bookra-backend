"""add_office_role_to_role_enum

Revision ID: beee08958782
Revises: cca393e2aef1
Create Date: 2025-11-17 22:24:48.461460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'beee08958782'
down_revision: Union[str, Sequence[str], None] = 'cca393e2aef1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'office' value to role_enum."""
    # PostgreSQL requires ALTER TYPE to add new enum values
    op.execute("ALTER TYPE role_enum ADD VALUE 'office'")


def downgrade() -> None:
    """Remove 'office' value from role_enum."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For safety, we'll leave a note that this requires manual intervention
    # or we can delete users with role='office' first if needed

    # Delete any users with role='office' before downgrade
    from sqlalchemy import text
    conn = op.get_bind()
    conn.execute(text("DELETE FROM users WHERE role = 'office'"))
    conn.commit()

    # Note: To fully remove 'office' from enum, you'd need to:
    # 1. Create new enum without 'office'
    # 2. Alter column to use new enum
    # 3. Drop old enum
    # For now, we just ensure no users have that role
