import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import create_app

app = create_app()


@pytest.mark.asyncio
async def test_cors_allowed_origin():
    """허용된 Origin 요청 시 Access-Control-Allow-Origin 및 Allow-Credentials 헤더 반환 검증"""
    allowed_origin = (
        [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()][0]
        if settings.CORS_ORIGINS
        else "http://localhost:3000"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 허용된 명시적 Origin 요청
        resp = await client.get(
            "/health",
            headers={"Origin": allowed_origin},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == allowed_origin
        assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_disallowed_origin():
    """비허용된 임의의 악성 Origin 요청 시 CORS 허용 헤더가 반환되지 않음을 검증"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/health",
            headers={"Origin": "https://attacker-site.com"},
        )
        assert resp.status_code == 200
        # 비허용 Origin은 access-control-allow-origin 헤더가 제공되지 않아 브라우저가 차단함
        assert "access-control-allow-origin" not in resp.headers


@pytest.mark.asyncio
async def test_cors_options_preflight_allowed_and_disallowed():
    """OPTIONS 프리플라이트 요청에 대한 정상 처리 및 비허용 Origin 거부 검증"""
    allowed_origin = (
        [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()][0]
        if settings.CORS_ORIGINS
        else "http://localhost:3000"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 허용 Origin 프리플라이트
        preflight_resp = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization",
            },
        )
        assert preflight_resp.status_code == 200
        assert (
            preflight_resp.headers.get("access-control-allow-origin") == allowed_origin
        )
        assert preflight_resp.headers.get("access-control-allow-credentials") == "true"
        assert "POST" in preflight_resp.headers.get("access-control-allow-methods", "")

        # 비허용 Origin 프리플라이트는 Starlette CORSMiddleware가 400 Bad Request로 거부
        bad_preflight = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://malicious-domain.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert bad_preflight.status_code == 400
        assert "access-control-allow-origin" not in bad_preflight.headers


def test_production_cors_origins_wildcard_rejected():
    """운영(production) 환경에서 CORS_ORIGINS에 와일드카드('*') 포함 시 기동 Fail-Fast 차단 검증"""
    from app.config import Settings

    valid_kwargs = {
        "ENV": "production",
        "JWT_SECRET_KEY": "secure-key-for-prod-32-characters!",
        "SMTP_USER": "test@example.com",
        "SMTP_PASSWORD": "password123",
    }

    # 단독 '*' 입력 시 차단
    with pytest.raises(
        ValueError, match="CRITICAL SECURITY: CORS_ORIGINS cannot contain wildcard"
    ):
        Settings(**valid_kwargs, CORS_ORIGINS="*")

    # 복수 Origin 및 공백 포함 와일드카드 입력 시 차단 ('https://ai0208.xyz, * , https://dont-paw-get.pages.dev')
    with pytest.raises(
        ValueError, match="CRITICAL SECURITY: CORS_ORIGINS cannot contain wildcard"
    ):
        Settings(
            **valid_kwargs,
            CORS_ORIGINS="https://ai0208.xyz,  *  , https://dont-paw-get.pages.dev",
        )


def test_staging_cors_origins_wildcard_rejected():
    """스테이징(staging) 환경에서 CORS_ORIGINS 와일드카드 포함 시 기동 차단 검증"""
    from app.config import Settings

    with pytest.raises(
        ValueError, match="CRITICAL SECURITY: CORS_ORIGINS cannot contain wildcard"
    ):
        Settings(
            ENV="staging",
            SMTP_USER="test@example.com",
            SMTP_PASSWORD="password123",
            CORS_ORIGINS="*",
        )


def test_production_cors_origins_explicit_allowed():
    """운영 환경에서 명시적 도메인 목록은 정상 통과 검증"""
    from app.config import Settings

    cfg = Settings(
        ENV="production",
        JWT_SECRET_KEY="secure-key-for-prod-32-characters!",
        SMTP_USER="test@example.com",
        SMTP_PASSWORD="password123",
        CORS_ORIGINS="https://ai0208.xyz, https://dont-paw-get.pages.dev",
    )
    assert cfg.ENV == "production"
    assert "https://ai0208.xyz" in cfg.CORS_ORIGINS


def test_local_environment_cors_wildcard_compatible():
    """로컬(local) 개발 환경에서는 기존 개발 편의성 유지를 위해 와일드카드 허용 검증"""
    from app.config import Settings

    local_cfg = Settings(ENV="local", CORS_ORIGINS="*")
    assert local_cfg.ENV == "local"
    assert local_cfg.CORS_ORIGINS == "*"
