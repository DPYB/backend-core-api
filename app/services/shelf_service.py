import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DefaultShelfCannotBeDeletedException,
    ShelfAccessDeniedException,
    ShelfNotFoundException,
)
from app.core.shelf_rank import ShelfRank
from app.models.library_book import LibraryBook
from app.models.shelf import Shelf
from app.schemas.shelf import (
    CreateShelfResponse,
    ShelfItemResponse,
    ShelfListResponse,
    UpdateShelfResponse,
)


class ShelfService:
    @staticmethod
    async def get_or_create_default_shelf(
        db: AsyncSession, member_id: uuid.UUID
    ) -> Shelf:
        """
        회원의 기본 책장을 가져오거나, 없으면 동시성 안전하게 생성하여 반환.
        """
        # 1. 기존 활성 기본 책장 조회
        stmt = select(Shelf).where(
            Shelf.member_id == member_id,
            Shelf.is_default.is_(True),
            Shelf.deleted_at.is_(None),
        )
        res = await db.execute(stmt)
        default_shelf = res.scalars().first()
        if default_shelf:
            return default_shelf

        # 2. 없으면 생성 시도 (동시성 경합 시 재시도)
        try:
            new_shelf = Shelf(
                member_id=member_id,
                name="기본 책장",
                is_default=True,
            )
            db.add(new_shelf)
            await db.commit()
            await db.refresh(new_shelf)
            return new_shelf
        except IntegrityError:
            await db.rollback()
            # 다른 요청에 의해 이미 생성되었을 경우 재조회
            stmt = select(Shelf).where(
                Shelf.member_id == member_id,
                Shelf.is_default.is_(True),
                Shelf.deleted_at.is_(None),
            )
            res = await db.execute(stmt)
            return res.scalars().one()

    @staticmethod
    async def create_shelf(
        db: AsyncSession, member_id: uuid.UUID, name: str
    ) -> CreateShelfResponse:
        shelf = Shelf(
            member_id=member_id,
            name=name.strip(),
            is_default=False,
        )
        db.add(shelf)
        await db.commit()
        await db.refresh(shelf)
        return CreateShelfResponse(
            shelf_id=shelf.id,
            name=shelf.name,
            is_default=shelf.is_default,
            created_at=shelf.created_at,
        )

    @staticmethod
    async def get_shelves(db: AsyncSession, member_id: uuid.UUID) -> ShelfListResponse:
        # 기본 책장 보장
        await ShelfService.get_or_create_default_shelf(db, member_id)

        # 도서 개수를 서브쿼리 또는 GROUP BY로 조회
        book_count_subquery = (
            select(
                LibraryBook.shelf_id,
                func.count(LibraryBook.id).label("book_count"),
            )
            .where(
                LibraryBook.member_id == member_id,
                LibraryBook.deleted_at.is_(None),
            )
            .group_by(LibraryBook.shelf_id)
            .subquery()
        )

        stmt = (
            select(
                Shelf,
                func.coalesce(book_count_subquery.c.book_count, 0).label("book_count"),
            )
            .outerjoin(book_count_subquery, Shelf.id == book_count_subquery.c.shelf_id)
            .where(
                Shelf.member_id == member_id,
                Shelf.deleted_at.is_(None),
            )
            .order_by(Shelf.is_default.desc(), Shelf.id.asc())
        )

        results = (await db.execute(stmt)).all()
        items = [
            ShelfItemResponse(
                shelf_id=shelf.id,
                name=shelf.name,
                is_default=shelf.is_default,
                book_count=count,
                created_at=shelf.created_at,
            )
            for shelf, count in results
        ]
        return ShelfListResponse(shelves=items)

    @staticmethod
    async def update_shelf(
        db: AsyncSession, member_id: uuid.UUID, shelf_id: int, name: str
    ) -> UpdateShelfResponse:
        stmt = select(Shelf).where(
            Shelf.id == shelf_id,
            Shelf.deleted_at.is_(None),
        )
        shelf = (await db.execute(stmt)).scalars().first()
        if not shelf:
            raise ShelfNotFoundException("책장을 찾을 수 없습니다.")
        if shelf.member_id != member_id:
            raise ShelfAccessDeniedException("해당 책장에 대한 권한이 없습니다.")

        shelf.name = name.strip()
        await db.commit()
        await db.refresh(shelf)
        return UpdateShelfResponse(
            shelf_id=shelf.id,
            name=shelf.name,
            is_default=shelf.is_default,
            updated_at=shelf.updated_at,
        )

    @staticmethod
    async def delete_shelf(
        db: AsyncSession, member_id: uuid.UUID, shelf_id: int
    ) -> None:
        stmt = select(Shelf).where(
            Shelf.id == shelf_id,
            Shelf.deleted_at.is_(None),
        )
        shelf = (await db.execute(stmt)).scalars().first()
        if not shelf:
            raise ShelfNotFoundException("책장을 찾을 수 없습니다.")
        if shelf.member_id != member_id:
            raise ShelfAccessDeniedException("해당 책장에 대한 권한이 없습니다.")
        if shelf.is_default:
            raise DefaultShelfCannotBeDeletedException(
                "기본 책장은 삭제할 수 없습니다."
            )

        # 기본 책장 조회
        default_shelf = await ShelfService.get_or_create_default_shelf(db, member_id)

        # 삭제할 책장의 도서들 조회
        books_stmt = (
            select(LibraryBook)
            .where(
                LibraryBook.shelf_id == shelf_id,
                LibraryBook.deleted_at.is_(None),
            )
            .order_by(LibraryBook.shelf_rank.asc())
        )
        books_to_move = (await db.execute(books_stmt)).scalars().all()

        if books_to_move:
            # 기본 책장의 마지막 shelf_rank 조회
            last_book_stmt = (
                select(LibraryBook)
                .where(
                    LibraryBook.shelf_id == default_shelf.id,
                    LibraryBook.deleted_at.is_(None),
                )
                .order_by(LibraryBook.shelf_rank.desc())
                .limit(1)
            )
            last_book = (await db.execute(last_book_stmt)).scalars().first()
            current_rank = last_book.shelf_rank if last_book else None

            for book in books_to_move:
                book.shelf_id = default_shelf.id
                if current_rank is None:
                    new_rank = ShelfRank.initial()
                else:
                    new_rank = ShelfRank.after(current_rank)
                book.shelf_rank = new_rank
                current_rank = new_rank

        # 책장 소프트 삭제
        shelf.deleted_at = datetime.now(UTC)
        await db.commit()
