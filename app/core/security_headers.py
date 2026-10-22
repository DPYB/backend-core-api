"""보안 응답 헤더(Security Headers) 순수 ASGI 미들웨어.

OWASP 권고 5대 표준 보안 헤더 및 CSP를 모든 HTTP 응답에 주입합니다:
- Strict-Transport-Security: max-age=31536000; includeSubDomains (HTTPS 강제)
- X-Content-Type-Options: nosniff (MIME 타입 스니핑 방어)
- X-Frame-Options: DENY (클릭재킹 방어)
- Referrer-Policy: strict-origin-when-cross-origin (리퍼러 정보 누출 최소화)
- Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=() (불필요 권한 비활성화)
- Content-Security-Policy:
  - API 일반 및 /openapi.json: default-src 'none'; frame-ancestors 'none';
  - /docs, /redoc: CDN(jsdelivr, Google Fonts) 및 Swagger UI 인라인 렌더링 호환 정책
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

DOCS_PATHS = frozenset({"/docs", "/docs/", "/redoc", "/redoc/"})

DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "frame-ancestors 'none';"
)

DEFAULT_API_CSP = "default-src 'none'; frame-ancestors 'none';"

COMMON_SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (
        b"permissions-policy",
        b"geolocation=(), camera=(), microphone=(), payment=()",
    ),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
]


class SecurityHeadersMiddleware:
    """모든 HTTP 응답(정상, 오류, 429 포함)에 표준 보안 헤더를 주입하는 순수 ASGI 미들웨어."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        # /docs 및 /redoc UI 페이지는 CDN 리소스 허용 CSP 적용, /openapi.json 포함 기타는 default-src 'none'
        csp_header_value = (
            DOCS_CSP.encode("latin-1")
            if path in DOCS_PATHS
            else DEFAULT_API_CSP.encode("latin-1")
        )

        headers_to_add: list[tuple[bytes, bytes]] = [
            *COMMON_SECURITY_HEADERS,
            (b"content-security-policy", csp_header_value),
        ]

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw_headers: list[tuple[bytes, bytes]] = list(
                    message.get("headers", [])
                )
                existing_keys = {k.lower() for k, _ in raw_headers}

                for key, value in headers_to_add:
                    if key not in existing_keys:
                        raw_headers.append((key, value))

                message["headers"] = raw_headers

            await send(message)

        await self.app(scope, receive, send_with_security_headers)
