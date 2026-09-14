import math
import uuid
from datetime import UTC, datetime

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BookAlreadyRegisteredException,
    InvalidFilterParameterException,
    InvalidPageValueException,
    InvalidReorderTargetException,
    LibraryBookAccessDeniedException,
    LibraryBookNotFoundException,
    ShelfAccessDeniedException,
    ShelfNotFoundException,
)
from app.core.shelf_rank import ShelfRank, ShelfRankExhaustedException
from app.models.enums import BookReadingStatus, GenreType
from app.models.library_book import LibraryBook
from app.models.scrap import Scrap
from app.models.shelf import Shelf
from app.schemas.common import PaginatedResponse
from app.schemas.library_book import (
    CreateLibraryBookRequest,
    CreateLibraryBookResponse,
    LibraryBookDetailResponse,
    LibraryBookItemResponse,
    MoveBookShelfResponse,
    ReorderBookResponse,
    UpdateLibraryBookRequest,
    UpdateLibraryBookResponse,
    UpdateProgressResponse,
)
from app.services.shelf_service import ShelfService


class BookService:
    @staticmethod
    async def create_book(
        db: AsyncSession, member_id: uuid.UUID, req: CreateLibraryBookRequest
    ) -> CreateLibraryBookResponse:
        # 1. 책장 확인 또는 기본 책장 배정
        shelf_id = req.shelf_id
        if shelf_id is None:
            default_shelf = await ShelfService.get_or_create_default_shelf(
                db, member_id
            )
            shelf_id = default_shelf.id
        else:
            shelf_stmt = select(Shelf).where(
                Shelf.id == shelf_id,
                Shelf.deleted_at.is_(None),
            )
            shelf = (await db.execute(shelf_stmt)).scalars().first()
            if not shelf:
                raise ShelfNotFoundException("책장을 찾을 수 없습니다.")
            if shelf.member_id != member_id:
                raise ShelfAccessDeniedException("해당 책장에 대한 권한이 없습니다.")

        # 2. ISBN 중복 확인
        clean_isbn = req.isbn.strip() if req.isbn else None
        if clean_isbn:
            dup_stmt = select(LibraryBook).where(
                LibraryBook.member_id == member_id,
                LibraryBook.isbn == clean_isbn,
                LibraryBook.deleted_at.is_(None),
            )
            dup = (await db.execute(dup_stmt)).scalars().first()
            if dup:
                raise BookAlreadyRegisteredException(
                    "이미 서재에 등록된 ISBN 도서입니다."
                )

        # 3. ShelfRank 계산 (소속 책장의 맨 마지막 뒤)
        last_book_stmt = (
            select(LibraryBook)
            .where(
                LibraryBook.shelf_id == shelf_id,
                LibraryBook.deleted_at.is_(None),
            )
            .order_by(LibraryBook.shelf_rank.desc())
            .limit(1)
        )
        last_book = (await db.execute(last_book_stmt)).scalars().first()
        if last_book:
            shelf_rank = ShelfRank.after(last_book.shelf_rank)
        else:
            shelf_rank = ShelfRank.initial()

        # 4. 페이지 유효성 검사 및 독서 상태/완독일시 자동 계산
        if req.total_pages is not None and req.current_page > req.total_pages:
            raise InvalidPageValueException(
                "현재 페이지는 전체 페이지를 초과할 수 없습니다."
            )

        status = req.reading_status
        completed_at = None
        if (
            req.total_pages is not None
            and req.total_pages > 0
            and req.current_page == req.total_pages
        ):
            status = BookReadingStatus.COMPLETED
            completed_at = datetime.now(UTC)
        elif status == BookReadingStatus.COMPLETED:
            completed_at = datetime.now(UTC)
        elif req.current_page > 0 and status == BookReadingStatus.PLANNED:
            status = BookReadingStatus.READING

        book = LibraryBook(
            member_id=member_id,
            shelf_id=shelf_id,
            shelf_rank=shelf_rank,
            title=req.title.strip(),
            author=req.author.strip(),
            isbn=clean_isbn,
            genre=req.genre,
            kdc=req.kdc.strip() if req.kdc else None,
            subject=req.subject.strip() if req.subject else None,
            publisher=req.publisher.strip() if req.publisher else None,
            published_date=req.published_date,
            cover_url=req.cover_url,
            reading_status=status,
            total_pages=req.total_pages,
            current_page=req.current_page,
            completed_at=completed_at,
        )
        db.add(book)
        await db.commit()
        await db.refresh(book)

        return CreateLibraryBookResponse(
            book_id=book.id,
            shelf_id=book.shelf_id,
            shelf_rank=book.shelf_rank,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            genre=book.genre,
            kdc=book.kdc,
            subject=book.subject,
            publisher=book.publisher,
            published_date=book.published_date,
            cover_url=book.cover_url,
            reading_status=book.reading_status,
            current_page=book.current_page,
            total_pages=book.total_pages,
            created_at=book.created_at,
            completed_at=book.completed_at,
        )

    @staticmethod
    async def get_books(
        db: AsyncSession,
        member_id: uuid.UUID,
        shelf_id: int | None = None,
        author: str | None = None,
        reading_status: str | None = None,
        genre: str | None = None,
        sort_by: str = "SHELF_ORDER",
        sort_order: str = "ASC",
        page: int = 0,
        size: int = 20,
    ) -> PaginatedResponse[LibraryBookItemResponse]:
        query = select(LibraryBook).where(
            LibraryBook.member_id == member_id,
            LibraryBook.deleted_at.is_(None),
        )

        # 필터링
        if shelf_id is not None:
            query = query.where(LibraryBook.shelf_id == shelf_id)
        if author is not None:
            query = query.where(LibraryBook.author == author.strip())
        if reading_status is not None:
            try:
                status_enum = BookReadingStatus(reading_status)
                query = query.where(LibraryBook.reading_status == status_enum)
            except ValueError:
                raise InvalidFilterParameterException(
                    "올바르지 않은 독서 상태 필터입니다."
                )
        if genre is not None:
            try:
                genre_enum = GenreType(genre)
                query = query.where(LibraryBook.genre == genre_enum)
            except ValueError:
                raise InvalidFilterParameterException("올바르지 않은 장르 필터입니다.")

        # 정렬 파라미터 검증
        valid_sort_by = {"SHELF_ORDER", "TITLE", "AUTHOR", "CREATED_AT", "PROGRESS"}
        valid_sort_order = {"ASC", "DESC"}
        if sort_by not in valid_sort_by:
            raise InvalidFilterParameterException(f"유효하지 않은 sortBy: {sort_by}")
        if sort_order not in valid_sort_order:
            raise InvalidFilterParameterException(
                f"유효하지 않은 sortOrder: {sort_order}"
            )

        is_desc = sort_order == "DESC"

        # 정렬 식 구성
        if sort_by == "SHELF_ORDER":
            sort_expr = (
                LibraryBook.shelf_rank.desc()
                if is_desc
                else LibraryBook.shelf_rank.asc()
            )
            query = query.order_by(sort_expr)
        elif sort_by == "TITLE":
            sort_expr = LibraryBook.title.desc() if is_desc else LibraryBook.title.asc()
            query = query.order_by(sort_expr)
        elif sort_by == "AUTHOR":
            sort_expr = (
                LibraryBook.author.desc() if is_desc else LibraryBook.author.asc()
            )
            query = query.order_by(sort_expr)
        elif sort_by == "CREATED_AT":
            sort_expr = (
                LibraryBook.created_at.desc()
                if is_desc
                else LibraryBook.created_at.asc()
            )
            query = query.order_by(sort_expr)
        elif sort_by == "PROGRESS":
            # total_pages가 있는 경우 (current_page * 100.0 / total_pages) 계산, 없으면 nulls last
            progress_calc = case(
                (
                    LibraryBook.total_pages > 0,
                    (LibraryBook.current_page * 100.0) / LibraryBook.total_pages,
                ),
                else_=None,
            )
            sort_expr = (
                progress_calc.desc().nulls_last()
                if is_desc
                else progress_calc.asc().nulls_last()
            )
            query = query.order_by(sort_expr, LibraryBook.id.asc())

        # 총 개수
        count_stmt = select(func.count()).select_from(query.subquery())
        total_elements = (await db.execute(count_stmt)).scalar() or 0
        total_pages = math.ceil(total_elements / size) if total_elements > 0 else 0

        # 페이징
        query = query.offset(page * size).limit(size)
        books = (await db.execute(query)).scalars().all()

        items = [
            LibraryBookItemResponse(
                book_id=b.id,
                shelf_id=b.shelf_id,
                shelf_rank=b.shelf_rank,
                title=b.title,
                author=b.author,
                isbn=b.isbn,
                genre=b.genre,
                kdc=b.kdc,
                subject=b.subject,
                publisher=b.publisher,
                cover_url=b.cover_url,
                reading_status=b.reading_status,
                current_page=b.current_page,
                total_pages=b.total_pages,
                created_at=b.created_at,
                completed_at=b.completed_at,
            )
            for b in books
        ]

        return PaginatedResponse[LibraryBookItemResponse](
            items=items,
            page=page,
            size=size,
            total_elements=total_elements,
            total_pages=total_pages,
            has_previous=page > 0,
            has_next=page < (total_pages - 1),
        )

    @staticmethod
    async def get_book_detail(
        db: AsyncSession, member_id: uuid.UUID, book_id: int
    ) -> LibraryBookDetailResponse:
        stmt = select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.deleted_at.is_(None),
        )
        book = (await db.execute(stmt)).scalars().first()
        if not book:
            raise LibraryBookNotFoundException("도서를 찾을 수 없습니다.")
        if book.member_id != member_id:
            raise LibraryBookAccessDeniedException(
                "해당 도서에 대한 접근 권한이 없습니다."
            )

        return LibraryBookDetailResponse(
            book_id=book.id,
            shelf_id=book.shelf_id,
            shelf_rank=book.shelf_rank,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            genre=book.genre,
            kdc=book.kdc,
            subject=book.subject,
            publisher=book.publisher,
            published_date=book.published_date,
            cover_url=book.cover_url,
            reading_status=book.reading_status,
            current_page=book.current_page,
            total_pages=book.total_pages,
            created_at=book.created_at,
            updated_at=book.updated_at,
            completed_at=book.completed_at,
        )

    @staticmethod
    async def update_book(
        db: AsyncSession,
        member_id: uuid.UUID,
        book_id: int,
        req: UpdateLibraryBookRequest,
    ) -> UpdateLibraryBookResponse:
        stmt = select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.deleted_at.is_(None),
        )
        book = (await db.execute(stmt)).scalars().first()
        if not book:
            raise LibraryBookNotFoundException("도서를 찾을 수 없습니다.")
        if book.member_id != member_id:
            raise LibraryBookAccessDeniedException(
                "해당 도서에 대한 접근 권한이 없습니다."
            )

        clean_isbn = req.isbn.strip() if req.isbn else None
        if clean_isbn and clean_isbn != book.isbn:
            dup_stmt = select(LibraryBook).where(
                LibraryBook.member_id == member_id,
                LibraryBook.isbn == clean_isbn,
                LibraryBook.id != book_id,
                LibraryBook.deleted_at.is_(None),
            )
            dup = (await db.execute(dup_stmt)).scalars().first()
            if dup:
                raise BookAlreadyRegisteredException(
                    "이미 서재에 등록된 ISBN 도서입니다."
                )

        if req.total_pages is not None and book.current_page > req.total_pages:
            raise InvalidPageValueException(
                "현재 페이지가 변경된 전체 페이지를 초과합니다."
            )

        new_status = req.reading_status
        if (
            req.total_pages is not None
            and req.total_pages > 0
            and book.current_page == req.total_pages
        ):
            new_status = BookReadingStatus.COMPLETED

        if new_status == BookReadingStatus.COMPLETED:
            if book.completed_at is None:
                book.completed_at = datetime.now(UTC)
        else:
            book.completed_at = None

        # ADR-0006: 11개 필드 전체 반영 (null 허용 필드는 null 전달 시 초기화)
        book.title = req.title.strip()
        book.author = req.author.strip()
        book.isbn = clean_isbn
        book.genre = req.genre
        book.kdc = req.kdc.strip() if req.kdc else None
        book.subject = req.subject.strip() if req.subject else None
        book.publisher = req.publisher.strip() if req.publisher else None
        book.published_date = req.published_date
        book.cover_url = req.cover_url
        book.reading_status = new_status
        book.total_pages = req.total_pages

        await db.commit()
        await db.refresh(book)

        return UpdateLibraryBookResponse(
            book_id=book.id,
            shelf_id=book.shelf_id,
            shelf_rank=book.shelf_rank,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            genre=book.genre,
            kdc=book.kdc,
            subject=book.subject,
            publisher=book.publisher,
            published_date=book.published_date,
            cover_url=book.cover_url,
            reading_status=book.reading_status,
            current_page=book.current_page,
            total_pages=book.total_pages,
            updated_at=book.updated_at,
            completed_at=book.completed_at,
        )

    @staticmethod
    async def delete_book(db: AsyncSession, member_id: uuid.UUID, book_id: int) -> None:
        stmt = select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.deleted_at.is_(None),
        )
        book = (await db.execute(stmt)).scalars().first()
        if not book:
            raise LibraryBookNotFoundException("도서를 찾을 수 없습니다.")
        if book.member_id != member_id:
            raise LibraryBookAccessDeniedException(
                "해당 도서에 대한 접근 권한이 없습니다."
            )

        now = datetime.now(UTC)
        # 1. 도서 소프트 삭제
        book.deleted_at = now

        # 2. 소속 스크랩 일괄 소프트 삭제 (불변식)
        scrap_stmt = (
            update(Scrap)
            .where(
                Scrap.book_id == book_id,
                Scrap.deleted_at.is_(None),
            )
            .values(deleted_at=now)
        )
        await db.execute(scrap_stmt)
        await db.commit()

    @staticmethod
    async def reorder_book(
        db: AsyncSession,
        member_id: uuid.UUID,
        book_id: int,
        before_book_id: int | None,
        after_book_id: int | None,
    ) -> ReorderBookResponse:
        # 본인 도서 확인
        stmt = select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.deleted_at.is_(None),
        )
        book = (await db.execute(stmt)).scalars().first()
        if not book:
            raise LibraryBookNotFoundException("도서를 찾을 수 없습니다.")
        if book.member_id != member_id:
            raise LibraryBookAccessDeniedException(
                "해당 도서에 대한 접근 권한이 없습니다."
            )

        # 자기 자신을 이웃으로 지정 불가
        if before_book_id == book_id or after_book_id == book_id:
            raise InvalidReorderTargetException(
                "자기 자신을 재정렬 대상으로 지정할 수 없습니다."
            )

        shelf_id = book.shelf_id

        # 책장의 모든 도서 순서대로 조회
        all_books_stmt = (
            select(LibraryBook)
            .where(
                LibraryBook.shelf_id == shelf_id,
                LibraryBook.deleted_at.is_(None),
            )
            .order_by(LibraryBook.shelf_rank.asc())
        )
        all_books = list((await db.execute(all_books_stmt)).scalars().all())

        # 이웃 도서 검증 및 prev_rank, next_rank 탐색
        target_id = before_book_id or after_book_id
        target_book = next((b for b in all_books if b.id == target_id), None)
        if not target_book:
            raise InvalidReorderTargetException(
                "지정된 대상 도서가 같은 책장에 존재하지 않습니다."
            )

        # 본인 제외한 리스트에서 타겟 위치 탐색
        remaining = [b for b in all_books if b.id != book_id]
        target_idx = next(i for i, b in enumerate(remaining) if b.id == target_id)

        if before_book_id is not None:
            # target_book 바로 '앞'으로 이동 -> prev는 target_idx - 1, next는 target_book
            prev_rank = remaining[target_idx - 1].shelf_rank if target_idx > 0 else None
            next_rank = target_book.shelf_rank
        else:
            # target_book 바로 '뒤'로 이동 -> prev는 target_book, next는 target_idx + 1
            prev_rank = target_book.shelf_rank
            next_rank = (
                remaining[target_idx + 1].shelf_rank
                if target_idx < len(remaining) - 1
                else None
            )

        try:
            new_rank = ShelfRank.between(prev_rank, next_rank)
            book.shelf_rank = new_rank
            await db.commit()
            await db.refresh(book)
        except (ShelfRankExhaustedException, ValueError):
            # 키 공간 소진 시 균등 재분배 (Rebalance)
            # 새 순서대로 배치
            if before_book_id is not None:
                new_ordered_list = (
                    remaining[:target_idx] + [book] + remaining[target_idx:]
                )
            else:
                new_ordered_list = (
                    remaining[: target_idx + 1] + [book] + remaining[target_idx + 1 :]
                )

            new_ranks = ShelfRank.rebalanced_sequence(len(new_ordered_list))
            for b, r in zip(new_ordered_list, new_ranks):
                b.shelf_rank = r
            await db.commit()
            await db.refresh(book)

        return ReorderBookResponse(
            book_id=book.id,
            shelf_id=book.shelf_id,
            shelf_rank=book.shelf_rank,
            updated_at=book.updated_at,
        )

    @staticmethod
    async def move_book_shelf(
        db: AsyncSession, member_id: uuid.UUID, book_id: int, target_shelf_id: int
    ) -> MoveBookShelfResponse:
        stmt = select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.deleted_at.is_(None),
        )
        book = (await db.execute(stmt)).scalars().first()
        if not book:
            raise LibraryBookNotFoundException("도서를 찾을 수 없습니다.")
        if book.member_id != member_id:
            raise LibraryBookAccessDeniedException(
                "해당 도서에 대한 접근 권한이 없습니다."
            )

        # 대상 책장 소유권 확인
        target_shelf_stmt = select(Shelf).where(
            Shelf.id == target_shelf_id,
            Shelf.deleted_at.is_(None),
        )
        target_shelf = (await db.execute(target_shelf_stmt)).scalars().first()
        if not target_shelf:
            raise ShelfNotFoundException("대상 책장을 찾을 수 없습니다.")
        if target_shelf.member_id != member_id:
            raise ShelfAccessDeniedException("대상 책장에 대한 권한이 없습니다.")

        # 대상 책장의 마지막 shelf_rank 조회
        last_book_stmt = (
            select(LibraryBook)
            .where(
                LibraryBook.shelf_id == target_shelf_id,
                LibraryBook.deleted_at.is_(None),
            )
            .order_by(LibraryBook.shelf_rank.desc())
            .limit(1)
        )
        last_book = (await db.execute(last_book_stmt)).scalars().first()
        if last_book:
            new_rank = ShelfRank.after(last_book.shelf_rank)
        else:
            new_rank = ShelfRank.initial()

        book.shelf_id = target_shelf_id
        book.shelf_rank = new_rank
        await db.commit()
        await db.refresh(book)

        return MoveBookShelfResponse(
            book_id=book.id,
            shelf_id=book.shelf_id,
            shelf_rank=book.shelf_rank,
            updated_at=book.updated_at,
        )

    @staticmethod
    async def update_progress(
        db: AsyncSession, member_id: uuid.UUID, book_id: int, current_page: int
    ) -> UpdateProgressResponse:
        stmt = select(LibraryBook).where(
            LibraryBook.id == book_id,
            LibraryBook.deleted_at.is_(None),
        )
        book = (await db.execute(stmt)).scalars().first()
        if not book:
            raise LibraryBookNotFoundException("도서를 찾을 수 없습니다.")
        if book.member_id != member_id:
            raise LibraryBookAccessDeniedException(
                "해당 도서에 대한 접근 권한이 없습니다."
            )

        if current_page < 0:
            raise InvalidPageValueException("진도 페이지 값은 0 이상이어야 합니다.")

        if book.total_pages is not None and current_page > book.total_pages:
            raise InvalidPageValueException(
                f"현재 페이지({current_page})는 전체 페이지({book.total_pages})를 초과할 수 없습니다."
            )

        book.current_page = current_page

        # 자동 상태 전이 및 completed_at 동기화
        if (
            book.total_pages is not None
            and book.total_pages > 0
            and current_page == book.total_pages
        ):
            book.reading_status = BookReadingStatus.COMPLETED
            if book.completed_at is None:
                book.completed_at = datetime.now(UTC)
        elif current_page > 0:
            book.reading_status = BookReadingStatus.READING
            book.completed_at = None
        else:
            # current_page == 0
            if book.reading_status == BookReadingStatus.COMPLETED:
                book.completed_at = None

        await db.commit()
        await db.refresh(book)

        calc_progress = (
            round((book.current_page / book.total_pages) * 100, 1)
            if (book.total_pages and book.total_pages > 0)
            else 0.0
        )

        return UpdateProgressResponse(
            book_id=book.id,
            current_page=book.current_page,
            total_pages=book.total_pages,
            progress=calc_progress,
            reading_status=book.reading_status,
            completed_at=book.completed_at,
            updated_at=book.updated_at,
        )
