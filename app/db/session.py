from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine_kwargs = {"echo": False}

if "asyncpg" in settings.DATABASE_URL:
    # Supabase Transaction Pooler (PgBouncer/Supavisor 6543 포트) 연동 시 충돌 방지
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
elif "sqlite" in settings.DATABASE_URL:
    # SQLite 인메모리 테스트 시 core, record, member 스키마를 기본 스키마로 투명 매핑
    engine_kwargs["execution_options"] = {
        "schema_translate_map": {"core": None, "record": None, "member": None}
    }

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
