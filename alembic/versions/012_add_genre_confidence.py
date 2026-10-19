"""add genre_confidence to core.library_book

Revision ID: 012_add_genre_confidence
Revises: 011_add_failed_attempts_to_email_verifications
Create Date: 2026-10-18 22:45:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012_add_genre_confidence"
down_revision: str | None = "011_add_failed_attempts_to_email_verifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE core.library_book ADD COLUMN IF NOT EXISTS genre_confidence FLOAT NULL;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE core.library_book DROP COLUMN IF EXISTS genre_confidence;")
