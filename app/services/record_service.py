import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.record import Record, RecordScrap
from app.schemas.record import RecordCreateRequest

logger = logging.getLogger(__name__)


class RecordService:
    @staticmethod
    async def create_record(
        db: AsyncSession, member_id: UUID, dto: RecordCreateRequest
    ) -> Record:
        # 1. 독서 기록 엔티티 생성
        record = Record(
            member_id=member_id,
            book_id=dto.book_id,
            title=dto.title,
            content=dto.content,
            rating=dto.rating,
            read_at=dto.read_at,
        )
        db.add(record)
        await db.flush()

        # 2. 포함된 스크랩 문장 생성
        if dto.scraps:
            for scrap_dto in dto.scraps:
                scrap = RecordScrap(
                    record_id=record.id,
                    member_id=member_id,
                    book_id=dto.book_id,
                    sentence=scrap_dto.sentence,
                    page_number=scrap_dto.page_number,
                    memo=scrap_dto.memo,
                    scrap_image_url=scrap_dto.scrap_image_url,
                )
                db.add(scrap)

        await db.commit()

        # scraps와 함께 다시 로드
        stmt = (
            select(Record)
            .options(selectinload(Record.scraps))
            .where(Record.id == record.id)
        )
        loaded_record = (await db.execute(stmt)).scalar_one()

        # 3. AI 에이전트 벡터화 요청 (백그라운드 비동기 호출)
        await RecordService.trigger_ai_vectorization(
            loaded_record.id, member_id, dto.title, dto.content
        )

        return loaded_record

    @staticmethod
    async def get_records(
        db: AsyncSession, member_id: UUID, skip: int = 0, limit: int = 20
    ) -> list[Record]:
        stmt = (
            select(Record)
            .options(selectinload(Record.scraps))
            .where(
                Record.member_id == member_id,
                Record.deleted_at.is_(None),
            )
            .order_by(Record.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_record_by_id(
        db: AsyncSession, member_id: UUID, record_id: int
    ) -> Record | None:
        stmt = (
            select(Record)
            .options(selectinload(Record.scraps))
            .where(
                Record.id == record_id,
                Record.member_id == member_id,
                Record.deleted_at.is_(None),
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_record(db: AsyncSession, member_id: UUID, record_id: int) -> bool:
        """독서 기록 소프트 삭제 시, 연결된 스크랩(Scrap)도 함께 논리 삭제(Soft Delete Cascade)한다."""
        now = datetime.now(UTC)

        # 1. 대상 독서 기록 확인
        record = await RecordService.get_record_by_id(db, member_id, record_id)
        if not record:
            return False

        # 2. 독서 기록 소프트 삭제
        record.deleted_at = now

        # 3. 연결된 스크랩 문장들도 함께 소프트 삭제 (Soft Delete Cascade 처리)
        await db.execute(
            update(RecordScrap)
            .where(
                RecordScrap.record_id == record_id,
                RecordScrap.member_id == member_id,
                RecordScrap.deleted_at.is_(None),
            )
            .values(deleted_at=now)
        )

        await db.commit()
        return True

    @staticmethod
    async def trigger_ai_vectorization(
        record_id: int, member_id: UUID, title: str, content: str
    ) -> None:
        """독서 기록 저장 완료 시 AI 에이전트에 벡터화 작업을 위임한다."""
        if not getattr(settings, "AI_AGENT_BASE_URL", None):
            return
        url = f"{settings.AI_AGENT_BASE_URL.rstrip('/')}/api/v1/vectors/records"
        payload = {
            "record_id": record_id,
            "member_id": str(member_id),
            "title": title,
            "content": content,
        }
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(url, json=payload)
        except Exception as e:
            logger.warning(
                f"AI Agent vectorization trigger failed (record_id={record_id}): {e}"
            )


record_service = RecordService()
