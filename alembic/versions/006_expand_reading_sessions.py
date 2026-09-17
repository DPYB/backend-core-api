"""expand reading_sessions with duration_seconds, start_time, end_time, memo, updated_at

Revision ID: 006_expand_reading_sessions
Revises: 005_add_reading_session_and_weather
Create Date: 2026-09-17 14:18:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_expand_reading_sessions"
down_revision: str | None = "005_add_reading_session_and_weather"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. record.reading_sessions 컬럼 확장
    op.execute(
        "ALTER TABLE record.reading_sessions ADD COLUMN IF NOT EXISTS duration_seconds INTEGER NULL;"
    )
    op.execute(
        "ALTER TABLE record.reading_sessions ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ NULL;"
    )
    op.execute(
        "ALTER TABLE record.reading_sessions ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ NULL;"
    )
    op.execute(
        "ALTER TABLE record.reading_sessions ADD COLUMN IF NOT EXISTS memo TEXT NULL;"
    )
    op.execute(
        "ALTER TABLE record.reading_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();"
    )

    # 기존 데이터가 있을 경우 duration_seconds = duration_minutes * 60, end_time = created_at으로 초기화
    op.execute(
        "UPDATE record.reading_sessions SET duration_seconds = duration_minutes * 60 WHERE duration_seconds IS NULL;"
    )
    op.execute(
        "UPDATE record.reading_sessions SET end_time = created_at WHERE end_time IS NULL;"
    )

    # 2. 인덱스 생성
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reading_sessions_member_month ON record.reading_sessions (member_id, end_time DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reading_sessions_book ON record.reading_sessions (book_id, created_at DESC);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS record.idx_reading_sessions_book;")
    op.execute("DROP INDEX IF EXISTS record.idx_reading_sessions_member_month;")
    op.execute("ALTER TABLE record.reading_sessions DROP COLUMN IF EXISTS updated_at;")
    op.execute("ALTER TABLE record.reading_sessions DROP COLUMN IF EXISTS memo;")
    op.execute("ALTER TABLE record.reading_sessions DROP COLUMN IF EXISTS end_time;")
    op.execute("ALTER TABLE record.reading_sessions DROP COLUMN IF EXISTS start_time;")
    op.execute(
        "ALTER TABLE record.reading_sessions DROP COLUMN IF EXISTS duration_seconds;"
    )
