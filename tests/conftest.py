import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 테스트 환경변수 설정
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["AUTH_DISABLED"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-12345678901234567890"

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# SQLite 인메모리 테스트 엔진 (schema_translate_map으로 core, record, member 스키마 투명 변환)
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    execution_options={
        "schema_translate_map": {"core": None, "record": None, "member": None}
    },
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

TEST_MEMBER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_MEMBER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(autouse=True)
async def prepare_database():
    """각 테스트마다 깨끗한 인메모리 DB 테이블 생성 및 삭제"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer mock-token-{TEST_MEMBER_ID}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def other_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """다른 회원(타인) 권한 테스트용 클라이언트"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer mock-token-{OTHER_MEMBER_ID}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
