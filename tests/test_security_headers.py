import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app

app = create_app()


@pytest.mark.asyncio
async def test_standard_security_headers_on_api_endpoints():
    """일반 API 응답에 OWASP 권고 5대 표준 보안 헤더와 엄격한 기본 CSP가 주입되는지 검증"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

        assert response.status_code == 200
        # 1. HSTS (preload 제외, max-age 및 includeSubDomains 확인)
        hsts = response.headers.get("strict-transport-security")
        assert hsts == "max-age=31536000; includeSubDomains"
        assert "preload" not in hsts

        # 2. X-Content-Type-Options
        assert response.headers.get("x-content-type-options") == "nosniff"

        # 3. X-Frame-Options
        assert response.headers.get("x-frame-options") == "DENY"

        # 4. Referrer-Policy
        assert (
            response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        )

        # 5. Permissions-Policy
        assert (
            response.headers.get("permissions-policy")
            == "geolocation=(), camera=(), microphone=(), payment=()"
        )

        # 6. 기본 API CSP
        assert (
            response.headers.get("content-security-policy")
            == "default-src 'none'; frame-ancestors 'none';"
        )


@pytest.mark.asyncio
async def test_security_headers_on_error_responses():
    """401, 404, 429 등 에러 응답에도 보안 헤더가 누락 없이 주입되는지 검증"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 404 Not Found
        res_404 = await client.get("/api/v1/non-existent-endpoint")
        assert res_404.status_code == 404
        assert res_404.headers.get("x-content-type-options") == "nosniff"
        assert res_404.headers.get("x-frame-options") == "DENY"
        assert (
            res_404.headers.get("content-security-policy")
            == "default-src 'none'; frame-ancestors 'none';"
        )

        # 401 Unauthorized
        res_401 = await client.get("/api/v1/users/me")
        assert res_401.status_code == 401
        assert res_401.headers.get("x-content-type-options") == "nosniff"
        assert res_401.headers.get("x-frame-options") == "DENY"
        assert (
            res_401.headers.get("strict-transport-security")
            == "max-age=31536000; includeSubDomains"
        )


@pytest.mark.asyncio
async def test_docs_and_redoc_csp_isolation_and_rendering():
    """/docs 및 /redoc는 CDN 허용 CSP가 적용되고 200 OK 렌더링되는지 검증"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # /docs Swagger UI
        res_docs = await client.get("/docs")
        assert res_docs.status_code == 200
        csp_docs = res_docs.headers.get("content-security-policy", "")
        assert "cdn.jsdelivr.net" in csp_docs
        assert "'unsafe-inline'" in csp_docs
        assert "frame-ancestors 'none'" in csp_docs
        assert res_docs.headers.get("x-frame-options") == "DENY"

        # /redoc
        res_redoc = await client.get("/redoc")
        assert res_redoc.status_code == 200
        csp_redoc = res_redoc.headers.get("content-security-policy", "")
        assert "cdn.jsdelivr.net" in csp_redoc

        # /openapi.json 은 UI가 아니므로 API 기본 CSP가 적용되어야 함
        res_openapi = await client.get("/openapi.json")
        assert res_openapi.status_code == 200
        assert (
            res_openapi.headers.get("content-security-policy")
            == "default-src 'none'; frame-ancestors 'none';"
        )
