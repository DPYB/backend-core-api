import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.library_book import LibraryBook
from app.models.reading_session import ReadingSession
from app.models.record import Record, RecordScrap
from app.models.scrap import Scrap
from app.models.shelf import Shelf
from app.services.demo_seed_data import DEMO_SEED_BOOKS_BY_ISBN, DEMO_SEED_ISBNS

logger = logging.getLogger("backend-core-api.demo_reset")
SEOUL_TZ = ZoneInfo("Asia/Seoul")


class DemoResetService:
    @staticmethod
    async def reset_demo_account(db: AsyncSession) -> dict[str, Any]:
        """
        데모 계정(DEMO_MEMBER_ID)의 데이터를 시드 상태로 멱등하게 복원합니다.
        1. 시드 도서 16종 외에 사용자가 추가 등록한 잉여 도서 및 연결 스크랩/세션 정리
        2. 시드 도서의 스크랩 중 시드 문장 외 추가된 잉여 스크랩 정리
        3. 시드 도서의 진도율, 독서 상태, 완독일시를 시드 기준값으로 원복
        4. 도서 소속 책장을 '기본 책장'으로 원복
        """
        demo_member_id = uuid.UUID(settings.DEMO_MEMBER_ID)

        # 0. 기본 책장 확인
        shelf_stmt = select(Shelf).where(
            Shelf.member_id == demo_member_id,
            Shelf.is_default.is_(True),
            Shelf.deleted_at.is_(None),
        )
        default_shelf = (await db.execute(shelf_stmt)).scalars().first()
        default_shelf_id = default_shelf.id if default_shelf else None

        # 1. 데모 계정의 현재 모든 도서 조회
        books_stmt = select(LibraryBook).where(LibraryBook.member_id == demo_member_id)
        all_books = (await db.execute(books_stmt)).scalars().all()

        surplus_books: list[LibraryBook] = []
        seed_books: list[LibraryBook] = []

        for b in all_books:
            if b.isbn in DEMO_SEED_ISBNS:
                seed_books.append(b)
            else:
                surplus_books.append(b)

        # 2. 잉여 도서 관련 데이터 삭제
        deleted_surplus_book_count = 0
        deleted_surplus_scrap_count = 0
        if surplus_books:
            surplus_book_ids = [b.id for b in surplus_books]
            # 잉여 도서의 독서 세션 삭제
            await db.execute(
                delete(ReadingSession).where(
                    ReadingSession.member_id == demo_member_id,
                    ReadingSession.book_id.in_(surplus_book_ids),
                )
            )
            # 잉여 도서의 독서 감상기록 및 연결 스크랩 삭제
            await db.execute(
                delete(RecordScrap).where(
                    RecordScrap.member_id == demo_member_id,
                    RecordScrap.book_id.in_(surplus_book_ids),
                )
            )
            await db.execute(
                delete(Record).where(
                    Record.member_id == demo_member_id,
                    Record.book_id.in_(surplus_book_ids),
                )
            )
            # 잉여 도서의 코어 스크랩 삭제
            del_scrap_res = await db.execute(
                delete(Scrap).where(Scrap.book_id.in_(surplus_book_ids))
            )
            deleted_surplus_scrap_count += getattr(del_scrap_res, "rowcount", 0) or 0

            # 잉여 도서 자체 삭제
            del_book_res = await db.execute(
                delete(LibraryBook).where(
                    LibraryBook.member_id == demo_member_id,
                    LibraryBook.id.in_(surplus_book_ids),
                )
            )
            deleted_surplus_book_count = getattr(
                del_book_res, "rowcount", len(surplus_books)
            ) or len(surplus_books)

        # 3. 시드 도서별 잉여 스크랩 삭제 및 진도율/완독상태 원복
        now_utc = datetime.now(UTC)
        now_kst = now_utc.astimezone(SEOUL_TZ)
        month_start_kst = now_kst.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_start_utc = month_start_kst.astimezone(UTC)

        restored_book_count = 0

        for book in seed_books:
            seed_meta = DEMO_SEED_BOOKS_BY_ISBN.get(book.isbn or "")
            if not seed_meta:
                continue

            # 3-1. 시드 정의 문장 외 추가된 스크랩 삭제
            seed_sentences = {s["sentence"] for s in seed_meta.get("scraps", [])}
            scraps_stmt = select(Scrap).where(
                Scrap.book_id == book.id,
                Scrap.deleted_at.is_(None),
            )
            book_scraps = (await db.execute(scraps_stmt)).scalars().all()
            for scrap in book_scraps:
                if scrap.sentence not in seed_sentences:
                    await db.delete(scrap)
                    deleted_surplus_scrap_count += 1

            # 3-2. 완독일시 계산 (이번 달 1일 이후 클램프)
            offset = seed_meta.get("completed_offset_days")
            if offset is not None:
                calc_completed = now_utc - timedelta(days=offset)
                completed_at_val = max(
                    calc_completed, month_start_utc + timedelta(hours=2)
                )
            else:
                completed_at_val = None

            # 3-3. 도서 필드 원복
            book.deleted_at = None
            if default_shelf_id:
                book.shelf_id = default_shelf_id
            book.current_page = seed_meta["current_page"]
            book.total_pages = seed_meta["total_pages"]
            book.reading_status = seed_meta["reading_status"]
            book.completed_at = completed_at_val
            restored_book_count += 1

        await db.commit()

        logger.info(
            "Demo account reset completed: %d surplus books deleted, %d surplus scraps deleted, %d seed books restored",
            deleted_surplus_book_count,
            deleted_surplus_scrap_count,
            restored_book_count,
        )

        return {
            "status": "SUCCESS",
            "member_id": str(demo_member_id),
            "deleted_surplus_books": deleted_surplus_book_count,
            "deleted_surplus_scraps": deleted_surplus_scrap_count,
            "restored_seed_books": restored_book_count,
            "reset_at": datetime.now(UTC).isoformat(),
        }
