"""add password_hash to member.members

Revision ID: 007_add_password_hash_to_members
Revises: 006_expand_reading_sessions
Create Date: 2026-09-19 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_add_password_hash_to_members"
down_revision: str | None = "006_expand_reading_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE member.members ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255) NULL;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE member.members DROP COLUMN IF EXISTS password_hash;")
