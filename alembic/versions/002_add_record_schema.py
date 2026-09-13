"""add record schema and tables

Revision ID: 002_add_record_schema
Revises: 001_initial_core_schema
Create Date: 2026-09-12 14:22:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_record_schema"
down_revision: str | None = "001_initial_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. record 격리 스키마 생성
    op.execute("CREATE SCHEMA IF NOT EXISTS record;")

    # 2. 독서 기록 원본 테이블 (record.records)
    op.execute("""
        CREATE TABLE IF NOT EXISTS record.records (
            id                BIGSERIAL PRIMARY KEY,
            member_id         UUID NOT NULL,
            book_id           BIGINT NOT NULL,
            title             VARCHAR(255) NOT NULL,
            content           TEXT NOT NULL,
            rating            INT CHECK (rating >= 1 AND rating <= 5),
            read_at           TIMESTAMPTZ,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at        TIMESTAMPTZ
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_records_member_id
            ON record.records (member_id, created_at DESC)
            WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_records_book_id
            ON record.records (book_id)
            WHERE deleted_at IS NULL;
    """)

    # 3. 문장 수집 스크랩 테이블 (record.scraps)
    op.execute("""
        CREATE TABLE IF NOT EXISTS record.scraps (
            id                BIGSERIAL PRIMARY KEY,
            record_id         BIGINT REFERENCES record.records(id) ON DELETE CASCADE,
            member_id         UUID NOT NULL,
            book_id           BIGINT NOT NULL,
            sentence          TEXT NOT NULL,
            page_number       INT,
            scrap_image_url   TEXT,
            memo              TEXT,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at        TIMESTAMPTZ
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_scraps_record_id
            ON record.scraps (record_id)
            WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_scraps_member_id
            ON record.scraps (member_id, created_at DESC)
            WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_scraps_book_id
            ON record.scraps (book_id)
            WHERE deleted_at IS NULL;
    """)

    # 4. updated_at 자동 갱신 트리거
    op.execute("""
        CREATE OR REPLACE FUNCTION record.update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE 'plpgsql';
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_records_updated_at ON record.records;")
    op.execute("""
        CREATE TRIGGER trg_records_updated_at
            BEFORE UPDATE ON record.records
            FOR EACH ROW
            EXECUTE FUNCTION record.update_updated_at_column();
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_scraps_updated_at ON record.scraps;")
    op.execute("""
        CREATE TRIGGER trg_scraps_updated_at
            BEFORE UPDATE ON record.scraps
            FOR EACH ROW
            EXECUTE FUNCTION record.update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS record.scraps CASCADE;")
    op.execute("DROP TABLE IF EXISTS record.records CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS record.update_updated_at_column CASCADE;")
