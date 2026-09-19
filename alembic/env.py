import asyncio
from logging.config import fileConfig

import sqlalchemy as sa
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401 (모든 모델을 등록하기 위해 임포트)
from alembic import context
from app.config import settings
from app.db.base import Base

# Alembic Config 객체
config = context.config

# 로깅 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target metadata
target_metadata = Base.metadata

# 환경변수의 DATABASE_URL 설정 반영 (configparser 보간 에러 방지를 위해 % -> %% 이스케이프)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    """오프라인 마이그레이션 실행"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="core",
        version_num_length=64,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # alembic_version 테이블이 core 스키마에 생성되므로 core, record, member 스키마 선행 보장 및 커밋
    with connection.begin():
        connection.execute(sa.text("CREATE SCHEMA IF NOT EXISTS core;"))
        connection.execute(sa.text("CREATE SCHEMA IF NOT EXISTS record;"))
        connection.execute(sa.text("CREATE SCHEMA IF NOT EXISTS member;"))
        connection.execute(
            sa.text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_schema = 'core' AND table_name = 'alembic_version' AND column_name = 'version_num'
                ) THEN
                    ALTER TABLE core.alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);
                END IF;
            END $$;
            """)
        )

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema="core",
        version_num_length=64,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """온라인 비동기 마이그레이션 실행"""
    configuration = config.get_section(config.config_ini_section, {})
    connect_args = {}
    if "asyncpg" in settings.DATABASE_URL:
        connect_args = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        }

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    # 로컬 개발 환경에서 실수로 공용 원격 Supabase DB의 마이그레이션을 돌리는 사고 방지
    if (
        settings.ENV == "local"
        and settings.is_remote_database()
        and not settings.ALLOW_REMOTE_MIGRATION
    ):
        raise RuntimeError(
            "\n[SAFETY INTERLOCK TRIGGERED]\n"
            "ENV='local' 환경에서 원격 공용 DB(Supabase)를 대상으로 마이그레이션 실행이 감지되었습니다.\n"
            "로컬에서 무단으로 마이그레이션을 실행하면 팀 공용 DB 스키마가 즉시 변경됩니다.\n"
            "팀원과 조율 후 원격 마이그레이션을 실행하려면 다음 환경변수를 지정하고 다시 시도하세요:\n"
            "  ALLOW_REMOTE_MIGRATION=true alembic upgrade head\n"
        )

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
