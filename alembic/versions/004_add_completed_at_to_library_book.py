"""add completed_at to library_book

Revision ID: 004_add_completed_at_to_library_book
Revises: 003_add_member_schema
Create Date: 2026-09-14 12:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_add_completed_at_to_library_book"
down_revision: str | None = "003_add_member_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE core.library_book ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ NULL;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE core.library_book DROP COLUMN IF EXISTS completed_at;")
