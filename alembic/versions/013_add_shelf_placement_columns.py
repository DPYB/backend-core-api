"""add shelf_tier and shelf_order to core.library_book

Revision ID: 013_add_shelf_placement_columns
Revises: 012_add_genre_confidence
Create Date: 2026-10-23 22:05:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013_add_shelf_placement_columns"
down_revision: str | None = "012_add_genre_confidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE core.library_book ADD COLUMN IF NOT EXISTS shelf_tier INT NOT NULL DEFAULT 0;"
    )
    op.execute(
        "ALTER TABLE core.library_book ADD COLUMN IF NOT EXISTS shelf_order INT NOT NULL DEFAULT 0;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_library_book_member_shelf_placement ON core.library_book (member_id, shelf_tier, shelf_order);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS core.ix_library_book_member_shelf_placement;")
    op.execute("ALTER TABLE core.library_book DROP COLUMN IF EXISTS shelf_order;")
    op.execute("ALTER TABLE core.library_book DROP COLUMN IF EXISTS shelf_tier;")
