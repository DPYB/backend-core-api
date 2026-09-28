"""add member.email_verifications table

Revision ID: 009_add_email_verifications
Revises: 008_update_baseline_terms_content
Create Date: 2026-09-28 16:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_add_email_verifications"
down_revision: str | None = "008_update_baseline_terms_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS member.email_verifications (
            id BIGSERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            code VARCHAR(10) NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_email_verifications_email
        ON member.email_verifications (email);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS member.email_verifications;")
