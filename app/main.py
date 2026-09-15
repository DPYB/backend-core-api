from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.base import Base
from app.db.session import engine
from app.routers import (
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 개발 및 테스트 환경 편의를 위해 테이블이 없는 경우 자동 생성 시도
    if settings.ENV in ("local", "test"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
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

    # 전역 예외 처리기 등록
    register_exception_handlers(app)

    # 라우터 등록
    app.include_router(health_router)
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
