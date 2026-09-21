import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.security import decode_jwt_token
from app.db.base import Base
from app.db.session import engine
from app.routers import (
    admin_router,
    auth_router,
    books_router,
    health_router,
    librarians_router,
    reading_sessions_router,
    records_router,
    reports_router,
    scraps_router,
    search_router,
    shelves_router,
    terms_router,
    users_router,
)

# Configure dual logging: console (stdout) + rotating file (logs/app.log)
log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
os.makedirs("logs", exist_ok=True)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Add handlers if not already present
file_handler = None
for h in root_logger.handlers:
    if isinstance(h, RotatingFileHandler):
        file_handler = h
        break

if not file_handler:
    file_handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

if not any(
    isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
    for h in root_logger.handlers
):
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

# Ensure uvicorn logs are captured in logs/app.log as well
for uvicorn_logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    u_logger = logging.getLogger(uvicorn_logger_name)
    if not any(isinstance(h, RotatingFileHandler) for h in u_logger.handlers):
        u_logger.addHandler(file_handler)

logger = logging.getLogger("backend-core-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 인메모리 테스트 환경(SQLite)이거나 명시적으로 AUTO_CREATE_TABLES가 켜진 경우에만 create_all 실행
    # 공용 Supabase DB 풀러를 가리키는 로컬 환경 등에서 암묵적 DDL 실행 및 스키마 불일치 방지
    should_auto_create = settings.AUTO_CREATE_TABLES or (
        settings.ENV == "test" and "sqlite" in settings.DATABASE_URL
    )
    if should_auto_create:
        logger.info(
            "Running Base.metadata.create_all for local/test schema initialization..."
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("Shutting down backend-core-api services...")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="backend-core-api",
        description="FastAPI Core API Service for Auth, Member, Virtual Shelf, Library Books, Scraps & Librarians",
        version="0.2.0",
        lifespan=lifespan,
    )

    # CORS 미들웨어 (Cloudflare 프론트엔드 도메인 및 로컬 주소 지원)
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 게스트 체험 모드 무결점 Read-Only 락 및 데모 계정 Allowlist 쓰기 가드 미들웨어
    # 데모 계정(DEMO_MEMBER_ID) 허용 쓰기 라우트 템플릿 (기타 모든 POST/PUT/PATCH/DELETE는 403 차단)
    demo_allowed_write_routes = {
        ("POST", "/api/v1/library/books"),
        ("PATCH", "/api/v1/library/books/{book_id}"),
        ("PATCH", "/api/v1/library/books/{book_id}/progress"),
        ("PATCH", "/api/v1/library/books/{book_id}/order"),
        ("PATCH", "/api/v1/library/books/{book_id}/shelf"),
        ("POST", "/api/v1/library/books/{book_id}/scraps"),
        ("PATCH", "/api/v1/library/scraps/{scrap_id}"),
        ("POST", "/api/v1/reading-sessions"),
        ("POST", "/api/v1/books/{book_id}/reading-sessions"),
        ("POST", "/api/v1/library/books/{book_id}/reading-sessions"),
        ("POST", "/api/v1/records"),
        ("PATCH", "/api/v1/librarians/{librarian_id}/representative"),
        ("PATCH", "/api/v1/librarians/{librarian_id}"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/refresh"),
    }

    @app.middleware("http")
    async def account_security_middleware(request: Request, call_next):
        # GET, HEAD, OPTIONS는 모든 사용자 및 게스트에게 항상 허용
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # 게스트 토큰 발급/연장 엔드포인트 자체는 POST 허용
        if request.url.path == "/api/v1/auth/guest":
            return await call_next(request)

        # Authorization 헤더 확인
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                payload = decode_jwt_token(token)
                sub_raw = str(payload.get("sub") or "")

                # 1. 게스트 토큰 (Read-Only) 차단
                if payload.get("role") == "guest" or sub_raw.startswith("guest-"):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "code": "GUEST_READONLY_MODE",
                            "message": "체험 모드(게스트)에서는 읽기 전용으로만 이용 가능합니다. 변경 작업을 수행하려면 로그인해 주세요.",
                        },
                    )

                # 2. 공개 데모 계정 (DEMO_MEMBER_ID) 쓰기 허용 목록(Allowlist) 가드
                if sub_raw == settings.DEMO_MEMBER_ID:
                    # FastAPI 라우트 템플릿 매칭 검사
                    matched = False
                    for route in request.app.routes:
                        match, _ = route.matches(request.scope)
                        if match.name == "FULL":
                            # 1) 일반 Route 인 경우
                            if (
                                hasattr(route, "path")
                                and (request.method, getattr(route, "path"))
                                in demo_allowed_write_routes
                            ):
                                matched = True
                                break
                            # 2) APIRouter include(_IncludedRouter) 된 하위 후보군 탐색
                            if hasattr(route, "effective_candidates"):
                                for cand in route.effective_candidates():
                                    cand_match, _ = cand.matches(request.scope)
                                    if cand_match.name == "FULL":
                                        cand_path = getattr(cand, "path", None)
                                        if (
                                            request.method,
                                            cand_path,
                                        ) in demo_allowed_write_routes:
                                            matched = True
                                            break
                            if matched:
                                break

                    if not matched:
                        logger.warning(
                            "Demo account attempted unauthorized mutation: %s %s",
                            request.method,
                            request.url.path,
                        )
                        return JSONResponse(
                            status_code=403,
                            content={
                                "code": "DEMO_ACCOUNT_PROTECTED",
                                "message": "데모 계정 보호 정책에 의해 허용되지 않는 변경 작업입니다.",
                            },
                        )

            except Exception:
                # 잘못된 토큰 등은 라우터/엔드포인트의 보안 의존성이 401로 적절히 처리하도록 통과
                pass

        return await call_next(request)

    # 전역 예외 처리기 등록
    register_exception_handlers(app)

    # 라우터 등록
    app.include_router(health_router)
    app.include_router(admin_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(terms_router)

    app.include_router(search_router)
    app.include_router(shelves_router)
    app.include_router(books_router)
    app.include_router(scraps_router)
    app.include_router(librarians_router)
    app.include_router(records_router)
    app.include_router(reading_sessions_router)
    app.include_router(reports_router)

    return app


app = create_app()
