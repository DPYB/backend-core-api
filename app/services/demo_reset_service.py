import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.shelf_rank import ShelfRank
from app.models.library_book import LibraryBook
from app.models.reading_session import ReadingSession
from app.models.record import Record, RecordScrap
from app.models.scrap import Scrap
from app.models.shelf import Shelf
from app.services.demo_seed_data import (
    DEMO_SEED_BOOKS_BY_ISBN,
    DEMO_SEED_ISBNS,
    GUEST_SEED_BOOKS_BY_ISBN,
    GUEST_SEED_ISBNS,
)

logger = logging.getLogger("backend-core-api.demo_reset")
SEOUL_TZ = ZoneInfo("Asia/Seoul")


class DemoResetService:
    @staticmethod
    async def reset_member_by_seed(
        db: AsyncSession,
        target_member_id: uuid.UUID,
        seed_isbns: set[str],
        seed_books_by_isbn: dict[str, Any],
        is_guest: bool = False,
    ) -> dict[str, Any]:
        """
        특정 계정(데모 또는 게스트)의 서재 데이터를 시드 상태로 멱등하게 복원합니다.
        1. 시드 도서 외 잉여 도서 및 연결 스크랩/세션/기록 삭제
        2. 시드 도서의 스크랩 중 잉여 스크랩 정리
        3. 시드 도서의 진도율, 독서 상태, 완독일시를 시드 기준값으로 원복
        4. 사용자가 삭제하여 누락된 시드 도서가 있는 경우 재등록 복구
        """
        # 0. 기본 책장 확인
        shelf_stmt = select(Shelf).where(
            Shelf.member_id == target_member_id,
            Shelf.is_default.is_(True),
            Shelf.deleted_at.is_(None),
        )
        default_shelf = (await db.execute(shelf_stmt)).scalars().first()
        default_shelf_id = default_shelf.id if default_shelf else None

        # 1. 대상 계정의 현재 모든 도서 조회
        books_stmt = select(LibraryBook).where(
            LibraryBook.member_id == target_member_id
        )
        all_books = (await db.execute(books_stmt)).scalars().all()

        surplus_books: list[LibraryBook] = []
        seed_books: list[LibraryBook] = []
        existing_isbns: set[str] = set()

        for b in all_books:
            if b.isbn in seed_isbns:
                seed_books.append(b)
                if b.isbn:
                    existing_isbns.add(b.isbn)
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
                    ReadingSession.member_id == target_member_id,
                    ReadingSession.book_id.in_(surplus_book_ids),
                )
            )
            # 잉여 도서의 독서 감상기록 및 연결 스크랩 삭제
            await db.execute(
                delete(RecordScrap).where(
                    RecordScrap.member_id == target_member_id,
                    RecordScrap.book_id.in_(surplus_book_ids),
                )
            )
            await db.execute(
                delete(Record).where(
                    Record.member_id == target_member_id,
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
                    LibraryBook.member_id == target_member_id,
                    LibraryBook.id.in_(surplus_book_ids),
                )
            )
            deleted_surplus_book_count = getattr(
                del_book_res, "rowcount", len(surplus_books)
            ) or len(surplus_books)

        # 3. 기존 시드 도서별 잉여 스크랩 삭제 및 진도율/완독상태 원복
        now_utc = datetime.now(UTC)
        now_kst = now_utc.astimezone(SEOUL_TZ)
        month_start_kst = now_kst.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_start_utc = month_start_kst.astimezone(UTC)

        restored_book_count = 0

        for book in seed_books:
            seed_meta = seed_books_by_isbn.get(book.isbn or "")
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

        # 4. 사용자가 삭제하여 누락된 시드 도서 재생성 (멱등 보장)
        recreated_book_count = 0
        if default_shelf_id:
            missing_isbns = [isbn for isbn in seed_isbns if isbn not in existing_isbns]
            if missing_isbns:
                ranks = ShelfRank.rebalanced_sequence(len(missing_isbns))
                for idx, m_isbn in enumerate(missing_isbns):
                    m_meta = seed_books_by_isbn.get(m_isbn)
                    if not m_meta:
                        continue
                    new_book = LibraryBook(
                        member_id=target_member_id,
                        shelf_id=default_shelf_id,
                        shelf_rank=ranks[idx],
                        title=m_meta["title"],
                        author=m_meta["author"],
                        isbn=m_isbn,
                        genre=m_meta["genre"],
                        kdc=m_meta["kdc"],
                        subject=m_meta["subject"],
                        publisher=m_meta["publisher"],
                        published_date=m_meta["published_date"],
                        cover_url=m_meta["cover_url"],
                        total_pages=m_meta["total_pages"],
                        current_page=m_meta["current_page"],
                        reading_status=m_meta["reading_status"],
                        completed_at=None,
                    )
                    db.add(new_book)
                    await db.flush()

                    for s_item in m_meta.get("scraps", []):
                        db.add(
                            Scrap(
                                book_id=new_book.id,
                                sentence=s_item["sentence"],
                                page_number=s_item["page_number"],
                                scrap_image_url=""
                                if is_guest
                                else (m_meta["cover_url"] or ""),
                                memo=s_item["memo"],
                            )
                        )
                    recreated_book_count += 1

        await db.commit()

        logger.info(
            "Account %s reset completed: %d surplus books deleted, %d surplus scraps deleted, %d seed books restored, %d recreated",
            target_member_id,
            deleted_surplus_book_count,
            deleted_surplus_scrap_count,
            restored_book_count,
            recreated_book_count,
        )

        return {
            "status": "SUCCESS",
            "member_id": str(target_member_id),
            "deleted_surplus_books": deleted_surplus_book_count,
            "deleted_surplus_scraps": deleted_surplus_scrap_count,
            "restored_seed_books": restored_book_count,
            "recreated_seed_books": recreated_book_count,
            "reset_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    async def reset_demo_account(db: AsyncSession) -> dict[str, Any]:
        """데모 계정(DEMO_MEMBER_ID, 16권) 시드 멱등 복원"""
        demo_member_id = uuid.UUID(settings.DEMO_MEMBER_ID)
        return await DemoResetService.reset_member_by_seed(
            db,
            target_member_id=demo_member_id,
            seed_isbns=DEMO_SEED_ISBNS,
            seed_books_by_isbn=DEMO_SEED_BOOKS_BY_ISBN,
            is_guest=False,
        )

    @staticmethod
    async def reset_guest_account(db: AsyncSession) -> dict[str, Any]:
        """게스트 계정(GUEST_MEMBER_ID, 9권) 시드 멱등 복원"""
        guest_member_id = uuid.UUID(settings.GUEST_MEMBER_ID)
        return await DemoResetService.reset_member_by_seed(
            db,
            target_member_id=guest_member_id,
            seed_isbns=GUEST_SEED_ISBNS,
            seed_books_by_isbn=GUEST_SEED_BOOKS_BY_ISBN,
            is_guest=True,
        )

    @staticmethod
    async def reset_accounts(db: AsyncSession, target: str = "all") -> dict[str, Any]:
        """target(all | demo | guest)에 따라 대상 계정 리셋 수행"""
        clean_target = (target or "all").strip().lower()
        if clean_target == "demo":
            res = await DemoResetService.reset_demo_account(db)
            return {"status": "SUCCESS", "target": "demo", "results": [res]}
        elif clean_target == "guest":
            res = await DemoResetService.reset_guest_account(db)
            return {"status": "SUCCESS", "target": "guest", "results": [res]}
        else:
            demo_res = await DemoResetService.reset_demo_account(db)
            guest_res = await DemoResetService.reset_guest_account(db)
            return {
                "status": "SUCCESS",
                "target": "all",
                "results": [demo_res, guest_res],
            }
