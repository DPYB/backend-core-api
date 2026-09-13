"""initial core schema and seed data

Revision ID: 001_initial_core_schema
Revises:
Create Date: 2026-09-11 13:10:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_core_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. core 스키마 생성
    op.execute("CREATE SCHEMA IF NOT EXISTS core;")

    # 2. ENUM 타입 생성
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE t.typname = 'genre_type' AND n.nspname = 'core') THEN
                CREATE TYPE core.genre_type AS ENUM (
                    'NONE', 'GENERAL', 'PHILOSOPHY', 'RELIGION', 'SOCIAL_SCIENCE',
                    'NATURAL_SCIENCE', 'TECHNOLOGY', 'ARTS', 'LANGUAGE', 'LITERATURE', 'HISTORY'
                );
            END IF;

            IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE t.typname = 'book_reading_status' AND n.nspname = 'core') THEN
                CREATE TYPE core.book_reading_status AS ENUM (
                    'PLANNED', 'READING', 'COMPLETED'
                );
            END IF;

            IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE t.typname = 'librarian_type' AND n.nspname = 'core') THEN
                CREATE TYPE core.librarian_type AS ENUM (
                    'CAT', 'SHOEBILL', 'SEA_SLUG', 'GECKO'
                );
            END IF;
        END$$;
    """)

    # 3. 테이블 생성
    # 3.1 core.shelf
    op.execute("""
        CREATE TABLE IF NOT EXISTS core.shelf (
            id BIGSERIAL PRIMARY KEY,
            member_id UUID NOT NULL,
            name VARCHAR(50) NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ NULL
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shelf_member_id ON core.shelf (member_id);"
    )
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uk_shelf_member_default ON core.shelf (member_id) 
            WHERE is_default = true AND deleted_at IS NULL;
    """)

    # 3.2 core.library_book
    op.execute("""
        CREATE TABLE IF NOT EXISTS core.library_book (
            id BIGSERIAL PRIMARY KEY,
            member_id UUID NOT NULL,
            shelf_id BIGINT NOT NULL REFERENCES core.shelf(id) ON DELETE RESTRICT,
            shelf_rank VARCHAR(128) NOT NULL,
            title VARCHAR(200) NOT NULL,
            author VARCHAR(100) NOT NULL,
            isbn VARCHAR(13) NULL,
            genre core.genre_type NOT NULL DEFAULT 'NONE',
            kdc VARCHAR(20) NULL,
            subject VARCHAR(100) NULL,
            publisher VARCHAR(100) NULL,
            published_date DATE NULL,
            cover_url TEXT NULL,
            reading_status core.book_reading_status NOT NULL DEFAULT 'PLANNED',
            total_pages INTEGER NULL,
            current_page INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ NULL
        );
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uk_library_book_shelf_rank ON core.library_book (shelf_id, shelf_rank) 
            WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uk_library_book_member_isbn ON core.library_book (member_id, isbn) 
            WHERE isbn IS NOT NULL AND deleted_at IS NULL;
    """)

    # 3.3 core.scrap
    op.execute("""
        CREATE TABLE IF NOT EXISTS core.scrap (
            id BIGSERIAL PRIMARY KEY,
            book_id BIGINT NOT NULL REFERENCES core.library_book(id) ON DELETE CASCADE,
            sentence TEXT NOT NULL,
            page_number INTEGER NULL,
            scrap_image_url TEXT NOT NULL,
            memo TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ NULL
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_scrap_book_id ON core.scrap (book_id);")

    # 3.4 core.librarian_type_info
    op.execute("""
        CREATE TABLE IF NOT EXISTS core.librarian_type_info (
            type core.librarian_type PRIMARY KEY,
            image_url TEXT NOT NULL,
            clicked_image_url TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # 3.5 core.librarian_level
    op.execute("""
        CREATE TABLE IF NOT EXISTS core.librarian_level (
            level INTEGER PRIMARY KEY,
            required_experience BIGINT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # 3.6 core.librarian
    op.execute("""
        CREATE TABLE IF NOT EXISTS core.librarian (
            id BIGSERIAL PRIMARY KEY,
            member_id UUID NOT NULL,
            type core.librarian_type NOT NULL REFERENCES core.librarian_type_info(type),
            name VARCHAR(50) NOT NULL,
            level INTEGER NOT NULL DEFAULT 1 REFERENCES core.librarian_level(level),
            experience BIGINT NOT NULL DEFAULT 0,
            is_representative BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at TIMESTAMPTZ NULL
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_librarian_member_id ON core.librarian (member_id) 
            WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uk_librarian_member_type ON core.librarian (member_id, type) 
            WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uk_librarian_member_representative ON core.librarian (member_id) 
            WHERE is_representative = true AND deleted_at IS NULL;
    """)

    # 4. 초기 시드 데이터 등록
    op.execute("""
        INSERT INTO core.librarian_type_info (type, image_url, clicked_image_url, created_at, updated_at)
        VALUES
          ('CAT', 'https://example.com/librarians/cat.png', 'https://example.com/librarians/cat-clicked.png', now(), now()),
          ('SHOEBILL', 'https://example.com/librarians/shoebill.png', 'https://example.com/librarians/shoebill-clicked.png', now(), now()),
          ('SEA_SLUG', 'https://example.com/librarians/sea-slug.png', 'https://example.com/librarians/sea-slug-clicked.png', now(), now()),
          ('GECKO', 'https://example.com/librarians/gecko.png', 'https://example.com/librarians/gecko-clicked.png', now(), now())
        ON CONFLICT (type) DO NOTHING;
    """)
    op.execute("""
        INSERT INTO core.librarian_level (level, required_experience, created_at, updated_at)
        VALUES (1, 0, now(), now())
        ON CONFLICT (level) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS core.librarian CASCADE;")
    op.execute("DROP TABLE IF EXISTS core.librarian_level CASCADE;")
    op.execute("DROP TABLE IF EXISTS core.librarian_type_info CASCADE;")
    op.execute("DROP TABLE IF EXISTS core.scrap CASCADE;")
    op.execute("DROP TABLE IF EXISTS core.library_book CASCADE;")
    op.execute("DROP TABLE IF EXISTS core.shelf CASCADE;")
    op.execute("DROP TYPE IF EXISTS core.librarian_type CASCADE;")
    op.execute("DROP TYPE IF EXISTS core.book_reading_status CASCADE;")
    op.execute("DROP TYPE IF EXISTS core.genre_type CASCADE;")
