from sqlalchemy import BigInteger, Integer, MetaData
from sqlalchemy.orm import DeclarativeBase

# Supabase PostgreSQL 'core' 스키마 격리
# (SQLite 테스트 환경에서는 schema_translate_map={"core": None}을 통해 단일 DB로 호환)
metadata = MetaData(schema="core")

# PostgreSQL에서는 BigInteger, SQLite에서는 autoincrement 지원을 위한 Integer 변형
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    metadata = metadata
