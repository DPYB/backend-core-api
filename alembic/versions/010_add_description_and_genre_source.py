"""add description and genre_source to library_book

Revision ID: 010_add_description_and_genre_source
Revises: 009_add_email_verifications
Create Date: 2026-10-07 16:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_add_description_and_genre_source"
down_revision: str | None = "009_add_email_verifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE core.library_book ADD COLUMN IF NOT EXISTS description TEXT NULL;"
    )
    op.execute(
        "ALTER TABLE core.library_book ADD COLUMN IF NOT EXISTS genre_source VARCHAR(20) NOT NULL DEFAULT 'KDC';"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE core.library_book DROP COLUMN IF EXISTS description;")
    op.execute("ALTER TABLE core.library_book DROP COLUMN IF EXISTS genre_source;")
