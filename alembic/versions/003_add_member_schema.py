"""add member schema and tables with baseline terms

Revision ID: 003_add_member_schema
Revises: 002_add_record_schema
Create Date: 2026-09-14 11:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_add_member_schema"
down_revision: str | None = "002_add_record_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. member 스키마 생성
    op.execute("CREATE SCHEMA IF NOT EXISTS member;")

    # 2. 회원 테이블 (member.members)
    op.execute("""
        CREATE TABLE IF NOT EXISTS member.members (
            id                BIGSERIAL PRIMARY KEY,
            member_id         UUID NOT NULL,
            email             VARCHAR(255) NOT NULL,
            nickname          VARCHAR(255) NOT NULL,
            profile_image_url TEXT,
            birth_date        DATE,
            gender            VARCHAR(20),
            status            VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
            provider          VARCHAR(50),
            provider_id       VARCHAR(255),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at        TIMESTAMPTZ
        );
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_members_member_id
            ON member.members (member_id);
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_members_email_active
            ON member.members (email)
            WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_members_provider
            ON member.members (provider, provider_id)
            WHERE deleted_at IS NULL;
    """)

    # 3. 약관 테이블 (member.terms)
    op.execute("""
        CREATE TABLE IF NOT EXISTS member.terms (
            id                BIGSERIAL PRIMARY KEY,
            code              VARCHAR(50) NOT NULL,
            name              VARCHAR(100) NOT NULL,
            content           TEXT NOT NULL,
            is_required       BOOLEAN NOT NULL DEFAULT false,
            effective_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            expired_at        TIMESTAMPTZ,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at        TIMESTAMPTZ,
            CONSTRAINT ck_terms_effective_period CHECK (expired_at IS NULL OR expired_at > effective_at)
        );
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uk_terms_active_code
            ON member.terms (code)
            WHERE expired_at IS NULL AND deleted_at IS NULL;
    """)

    # 4. 약관 동의/철회 이력 테이블 (member.member_agreements)
    op.execute("""
        CREATE TABLE IF NOT EXISTS member.member_agreements (
            id                BIGSERIAL PRIMARY KEY,
            member_id         UUID NOT NULL,
            terms_id          BIGINT NOT NULL REFERENCES member.terms(id) ON DELETE CASCADE,
            action            VARCHAR(20) NOT NULL DEFAULT 'AGREE',
            occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at        TIMESTAMPTZ
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_member_agreements_member_terms
            ON member.member_agreements (member_id, terms_id, occurred_at DESC)
            WHERE deleted_at IS NULL;
    """)

    # 5. updated_at 자동 갱신 트리거
    op.execute("""
        CREATE OR REPLACE FUNCTION member.update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE 'plpgsql';
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_members_updated_at ON member.members;")
    op.execute("""
        CREATE TRIGGER trg_members_updated_at
            BEFORE UPDATE ON member.members
            FOR EACH ROW
            EXECUTE FUNCTION member.update_updated_at_column();
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_terms_updated_at ON member.terms;")
    op.execute("""
        CREATE TRIGGER trg_terms_updated_at
            BEFORE UPDATE ON member.terms
            FOR EACH ROW
            EXECUTE FUNCTION member.update_updated_at_column();
    """)
    op.execute(
        "DROP TRIGGER IF EXISTS trg_member_agreements_updated_at ON member.member_agreements;"
    )
    op.execute("""
        CREATE TRIGGER trg_member_agreements_updated_at
            BEFORE UPDATE ON member.member_agreements
            FOR EACH ROW
            EXECUTE FUNCTION member.update_updated_at_column();
    """)

    # 6. 기본 약관 3종 시드 데이터 적재
    op.execute("""
        INSERT INTO member.terms (code, name, content, is_required, effective_at)
        VALUES
        (
            'TERMS_OF_SERVICE',
            '서비스 이용약관',
            '제1조 (목적)\n본 약관은 dont-paw-get(이하 "서비스")의 이용 조건 및 절차, 이용자와 서비스 간의 권리, 의무 및 책임사항을 규정함을 목적으로 합니다.\n\n제2조 (회원의 권리와 의무)\n회원은 관련 법령 및 본 약관의 규정을 준수하여야 하며 타인의 권리를 침해하지 않아야 합니다.',
            true,
            now()
        ),
        (
            'PRIVACY',
            '개인정보 처리방침',
            '제1조 (개인정보의 수집 및 이용 목적)\n회원 식별, 서비스 제공, 독서 기록 영속화 및 맞춤형 사서 서비스 제공을 위해 최소한의 개인정보(이메일, 닉네임, 프로필 이미지 등)를 수집합니다.\n\n제2조 (개인정보의 보유 및 이용 기간)\n회원 탈퇴 시 또는 법정 보존 기간 경과 시까지 안전하게 보관 및 파기됩니다.',
            true,
            now()
        ),
        (
            'AI_ANALYSIS',
            'AI 독서 분석 서비스 이용 동의',
            '제1조 (AI 분석 목적)\n이용자가 작성한 독서 감상평 및 문장 스크랩을 기반으로 도서 추천, AI 사서 대화, 독서 성향 분석을 제공하기 위해 데이터를 처리합니다.\n\n제2조 (선택 동의 철회)\n본 동의는 선택 사항이며 언제든지 철회할 수 있습니다.',
            false,
            now()
        )
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS member.member_agreements CASCADE;")
    op.execute("DROP TABLE IF EXISTS member.terms CASCADE;")
    op.execute("DROP TABLE IF EXISTS member.members CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS member.update_updated_at_column CASCADE;")
