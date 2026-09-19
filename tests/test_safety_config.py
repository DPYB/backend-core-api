import pytest

from app.config import Settings


def test_production_jwt_secret_validation():
    """운영 환경(ENV=production)에서 취약한 기본 JWT 시크릿 방치 시 fail-fast 검증"""
    with pytest.raises(ValueError, match="CRITICAL SECURITY: JWT_SECRET_KEY must be configured"):
        Settings(
            ENV="production",
            JWT_SECRET_KEY="dont-paw-get-jwt-secret-change-in-prod-2026",
        )


def test_production_jwt_secret_valid():
    """운영 환경(ENV=production)에서 안전한 커스텀 JWT 시크릿 설정 시 정상 초기화 검증"""
    cfg = Settings(
        ENV="production",
        JWT_SECRET_KEY="a-secure-production-random-secret-key-value",
    )
    assert cfg.JWT_SECRET_KEY == "a-secure-production-random-secret-key-value"


def test_remote_database_detection():
    """원격 Supabase 또는 클라우드 DB 호스트 감지 로직 검증"""
    cfg_remote = Settings(DATABASE_URL="postgresql+asyncpg://user:pass@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres")
    assert cfg_remote.is_remote_database() is True

    cfg_local = Settings(DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres")
    assert cfg_local.is_remote_database() is False
