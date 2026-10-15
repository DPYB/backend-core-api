"""add failed_attempts to member.email_verifications

Revision ID: 011_add_failed_attempts_to_email_verifications
Revises: 010_add_description_and_genre_source
Create Date: 2026-10-16 00:55:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011_add_failed_attempts_to_email_verifications"
down_revision: str | None = "010_add_description_and_genre_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE member.email_verifications ADD COLUMN IF NOT EXISTS failed_attempts INT NOT NULL DEFAULT 0;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE member.email_verifications DROP COLUMN IF EXISTS failed_attempts;"
    )
