"""add reading_sessions and weather to records

Revision ID: 005_add_reading_session_and_weather
Revises: 004_add_completed_at_to_library_book
Create Date: 2026-09-15 11:47:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_add_reading_session_and_weather"
down_revision: str | None = "004_add_completed_at_to_library_book"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. record.records에 weather 컬럼 추가
    op.execute(
        "ALTER TABLE record.records ADD COLUMN IF NOT EXISTS weather VARCHAR(50) NULL;"
    )

    # 2. record.reading_sessions 테이블 신설 (스톱워치 독서 세션 로그 영속화)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS record.reading_sessions (
            id BIGSERIAL PRIMARY KEY,
            member_id UUID NOT NULL,
            book_id BIGINT NULL,
            duration_minutes INTEGER NOT NULL,
            start_page INTEGER NULL,
            end_page INTEGER NULL,
            weather VARCHAR(50) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    # 3. 인덱스 생성
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reading_sessions_member_id ON record.reading_sessions (member_id, created_at DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_reading_sessions_book_id ON record.reading_sessions (book_id, created_at DESC);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS record.ix_reading_sessions_book_id;")
    op.execute("DROP INDEX IF EXISTS record.ix_reading_sessions_member_id;")
    op.execute("DROP TABLE IF EXISTS record.reading_sessions;")
    op.execute("ALTER TABLE record.records DROP COLUMN IF EXISTS weather;")
