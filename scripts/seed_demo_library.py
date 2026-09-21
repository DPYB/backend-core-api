"""
데모 계정(dpyb26@gmail.com) 풍성한 서재(16권), 스크랩 문장, 독서 세션, 사서 4종 시드 스크립트.

기능 및 안전장치:
1. --reset 옵션: 회원의 기존 도서, 스크랩, 감상기록, 독서 세션 전체를 hard delete 리셋 (외래키 순서 준수)
2. --yes 옵션: 원격/운영 DB 가드 확인 플래그 (누락 시 대화형 프롬프트 또는 중단)
3. 상대 날짜(Relative Date): 오늘(Now) 기준 상대적 과거 날짜로 배치하여 시연 월(9월, 10월 등)과 무관하게 '이번 달 리포트' 통계 보장
4. KST 기준 시간대 정렬: Asia/Seoul 기준 시간대(새벽 5~6시 포함)로 생성 후 UTC 변환 저장
5. 이번 달 리포트 클램프: 모든 세션 및 완독 날짜를 '이번 달 1일(KST)' 이후로 클램프하여 월간 리포트 반영
6. 서지정보 정비: 까치글방 《침묵의 세계》, 인플루엔셜 《돈의 심리학》, 민음사 《달과 6펜스》 등 국립중앙도서관 공식 서지정보 및 교보문고 표지 매핑
7. 대표 사서 단일성 보장: CAT(블루) 대표 지정 시 타 사서 대표 플래그 일괄 False 해제
8. random.seed 고정: 리허설 및 시연 결과 동일 재현 가능

실행 방법:
    python scripts/seed_demo_library.py --yes
    python scripts/seed_demo_library.py --reset --yes
"""

import argparse
import asyncio
import hashlib
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# 프로젝트 루트를 sys.path에 추가하여 python scripts/... 실행 시 app 패키지 인식 보장
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import delete, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.shelf_rank import ShelfRank  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.enums import (  # noqa: E402
    DEFAULT_LIBRARIAN_NAMES,
    BookReadingStatus,
    LibrarianType,
)
from app.models.librarian import Librarian  # noqa: E402
from app.models.library_book import LibraryBook  # noqa: E402
from app.models.reading_session import ReadingSession  # noqa: E402
from app.models.record import Record, RecordScrap  # noqa: E402
from app.models.scrap import Scrap  # noqa: E402
from app.models.shelf import Shelf  # noqa: E402
from app.services.demo_seed_data import DEMO_SEED_BOOKS  # noqa: E402
from app.services.librarian_service import LibrarianService  # noqa: E402
from app.services.member_service import MemberService  # noqa: E402

TARGET_EMAIL = "dpyb26@gmail.com"
SEOUL_TZ = ZoneInfo("Asia/Seoul")

# 단일 진실 공급원(SSOT) 재사용
SEED_BOOKS = DEMO_SEED_BOOKS


def check_db_guard(auto_yes: bool) -> None:
    """DB 연결 호스트 및 안전 가드 확인"""
    db_host = settings.DB_HOST or "localhost"
    is_remote = settings.is_remote_database()
    print("=" * 60)
    print(f"📌 대상 DB 호스트: {db_host} (원격 DB 여부: {is_remote})")
    print(f"📌 대상 계정: {TARGET_EMAIL}")
    print("=" * 60)

    if not auto_yes:
        confirm = (
            input("위 대상 DB에 시드 데이터를 적재하시겠습니까? (yes/no): ")
            .strip()
            .lower()
        )
        if confirm not in ("yes", "y"):
            print("🚫 작업을 취소했습니다.")
            sys.exit(0)


def generate_pseudo_embedding(text_content: str, dimension: int = 768) -> list[float]:
    """backend-ai-agent의 768차원 결정론적 임베딩 생성기와 100% 동일한 벡터 생성"""
    seed = int(hashlib.md5(text_content.encode("utf-8")).hexdigest(), 16)
    vector = [((seed + i * 37) % 1000) / 1000.0 for i in range(dimension)]
    norm = sum(x * x for x in vector) ** 0.5 or 1.0
    return [x / norm for x in vector]


async def reset_member_data(db: AsyncSession, member_id: uuid.UUID) -> None:
    """회원의 기존 서재 도서, 스크랩, 감상기록, 독서 세션 전체를 hard delete 리셋 (FK 자식 -> 부모 순)"""
    print(
        f"\n🧹 [--reset] {TARGET_EMAIL} 회원의 기존 데이터 전면 초기화(hard delete) 진행..."
    )
    book_ids_stmt = select(LibraryBook.id).where(LibraryBook.member_id == member_id)

    # 1. core & record 스키마 FK 역순 삭제: scraps, records, reading_sessions, library_book
    await db.execute(delete(RecordScrap).where(RecordScrap.member_id == member_id))
    await db.execute(delete(Record).where(Record.member_id == member_id))
    await db.execute(
        delete(ReadingSession).where(ReadingSession.member_id == member_id)
    )
    await db.execute(delete(Scrap).where(Scrap.book_id.in_(book_ids_stmt)))
    await db.execute(delete(LibraryBook).where(LibraryBook.member_id == member_id))
    await db.commit()  # core/record 메인 데이터 먼저 안전하게 확정

    # 2. agent 스키마 토론 인사이트 삭제 (SAVEPOINT 격리: 실패해도 core 데이터 영향 없음)
    try:
        async with db.begin_nested():
            await db.execute(
                text("DELETE FROM agent.debate_insights WHERE member_id = :mid"),
                {"mid": member_id},
            )
        await db.commit()
    except Exception as e:
        print(f"참고: agent.debate_insights 초기화 건너뜀 ({e})")

    print(f"-> {TARGET_EMAIL} 회원의 기존 도서/스크랩/기록/세션/토론기억 초기화 완료!")


async def seed_demo_library(auto_yes: bool = False, reset_mode: bool = False) -> None:
    # 재현성을 위한 난수 시드 고정
    random.seed(42)

    check_db_guard(auto_yes)

    async with AsyncSessionLocal() as db:
        print(f"\n[{TARGET_EMAIL}] 데모 계정 서재 시드 작업 시작...")

        # 1. 회원 조회 또는 생성
        member, is_new = await MemberService.get_or_create_dev_member(db, TARGET_EMAIL)
        member_id = member.member_id
        print(f"-> 대상 회원 ID: {member_id} (신규 생성: {is_new})")

        # --reset 요청 시 회원의 기존 도서/스크랩/세션 전체 초기화
        if reset_mode:
            await reset_member_data(db, member_id)

        # 2. 사서 마스터 시드 확인 및 4종 풀세트 언락 (단일 대표 사서 보장)
        await LibrarianService.ensure_seed_data(db)

        # 기존 사서 조회
        existing_libs_stmt = select(Librarian).where(
            Librarian.member_id == member_id,
            Librarian.deleted_at.is_(None),
        )
        existing_libs = (await db.execute(existing_libs_stmt)).scalars().all()
        owned_types = {lib.type: lib for lib in existing_libs}

        for l_type in [
            LibrarianType.CAT,
            LibrarianType.SHOEBILL,
            LibrarianType.SEA_SLUG,
            LibrarianType.GECKO,
        ]:
            if l_type not in owned_types:
                new_lib = Librarian(
                    member_id=member_id,
                    type=l_type,
                    name=DEFAULT_LIBRARIAN_NAMES.get(l_type, str(l_type)),
                    level=1,
                    experience=0,
                    is_representative=(l_type == LibrarianType.CAT),
                )
                db.add(new_lib)
            else:
                # CAT만 대표 사서로 보장하고 나머지는 반드시 False로 강제 해제 (단일 대표 사서 불변식)
                owned_types[l_type].is_representative = l_type == LibrarianType.CAT
                owned_types[l_type].level = 1

        await db.commit()
        print(
            "-> 사서 4종 풀세트 언락 완료 (대표 사서: '블루' 고양이 Lv.1 단일 대표 보장)"
        )

        # 3. 기본 책장 확인
        shelf_stmt = select(Shelf).where(
            Shelf.member_id == member_id,
            Shelf.is_default.is_(True),
            Shelf.deleted_at.is_(None),
        )
        default_shelf = (await db.execute(shelf_stmt)).scalars().first()
        if not default_shelf:
            default_shelf = Shelf(
                member_id=member_id,
                name="기본 책장",
                is_default=True,
            )
            db.add(default_shelf)
            await db.commit()
            await db.refresh(default_shelf)
        print(f"-> 기본 책장 ID: {default_shelf.id}")

        # 4. 상대 날짜(Relative Date) 기준점 계산
        # 이번 달 리포트에 100% 반영되도록 KST 기준 이번 달 1일(month_start_utc)을 하한선으로 설정
        now_utc = datetime.now(UTC)
        now_kst = now_utc.astimezone(SEOUL_TZ)
        month_start_kst = now_kst.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_start_utc = month_start_kst.astimezone(UTC)

        ranks = ShelfRank.rebalanced_sequence(len(SEED_BOOKS))
        created_books: list[LibraryBook] = []

        for idx, book_data in enumerate(SEED_BOOKS):
            rank = ranks[idx]
            isbn = book_data["isbn"]

            # 완독일 계산 (오늘 기준 -N일, 단 이번 달 1일 이후로 클램프)
            offset = book_data["completed_offset_days"]
            if offset is not None:
                calc_completed = now_utc - timedelta(days=offset)
                completed_at_val = max(
                    calc_completed, month_start_utc + timedelta(hours=2)
                )
            else:
                completed_at_val = None

            existing_book_stmt = select(LibraryBook).where(
                LibraryBook.member_id == member_id,
                LibraryBook.isbn == isbn,
            )
            book = (await db.execute(existing_book_stmt)).scalars().first()

            if book:
                book.deleted_at = None
                book.shelf_id = default_shelf.id
                book.shelf_rank = rank
                book.title = book_data["title"]
                book.author = book_data["author"]
                book.genre = book_data["genre"]
                book.kdc = book_data["kdc"]
                book.subject = book_data["subject"]
                book.publisher = book_data["publisher"]
                book.published_date = book_data["published_date"]
                book.cover_url = book_data["cover_url"]
                book.total_pages = book_data["total_pages"]
                book.current_page = book_data["current_page"]
                book.reading_status = book_data["reading_status"]
                book.completed_at = completed_at_val
            else:
                book = LibraryBook(
                    member_id=member_id,
                    shelf_id=default_shelf.id,
                    shelf_rank=rank,
                    title=book_data["title"],
                    author=book_data["author"],
                    isbn=isbn,
                    genre=book_data["genre"],
                    kdc=book_data["kdc"],
                    subject=book_data["subject"],
                    publisher=book_data["publisher"],
                    published_date=book_data["published_date"],
                    cover_url=book_data["cover_url"],
                    total_pages=book_data["total_pages"],
                    current_page=book_data["current_page"],
                    reading_status=book_data["reading_status"],
                    completed_at=completed_at_val,
                )
                db.add(book)

            await db.flush()
            created_books.append(book)

            # 5. 스크랩 문장 및 감상기록 생성 (과거 11권만 생성, created_at 분산)
            for scrap_item in book_data["scraps"]:
                # 스크랩 및 감상기록 일시는 완독일 직전 또는 최근 며칠 전으로 분산 (이번 달 범위 내)
                ref_time = completed_at_val or now_utc
                target_created_at = max(
                    ref_time - timedelta(hours=random.randint(1, 36)),
                    month_start_utc + timedelta(hours=1),
                )

                dup_core_scrap = (
                    (
                        await db.execute(
                            select(Scrap).where(
                                Scrap.book_id == book.id,
                                Scrap.sentence == scrap_item["sentence"],
                                Scrap.deleted_at.is_(None),
                            )
                        )
                    )
                    .scalars()
                    .first()
                )

                if not dup_core_scrap:
                    core_scrap = Scrap(
                        book_id=book.id,
                        sentence=scrap_item["sentence"],
                        page_number=scrap_item["page_number"],
                        scrap_image_url=book.cover_url or "",
                        memo=scrap_item["memo"],
                        created_at=target_created_at,
                    )
                    db.add(core_scrap)

                dup_rec_scrap = (
                    (
                        await db.execute(
                            select(RecordScrap).where(
                                RecordScrap.member_id == member_id,
                                RecordScrap.book_id == book.id,
                                RecordScrap.sentence == scrap_item["sentence"],
                                RecordScrap.deleted_at.is_(None),
                            )
                        )
                    )
                    .scalars()
                    .first()
                )

                if not dup_rec_scrap:
                    new_rec = Record(
                        member_id=member_id,
                        book_id=book.id,
                        title=f"《{book.title}》 감상",
                        content=f"{book.title}을(를) 읽으며 가장 마음에 남았던 문장입니다. {scrap_item['memo']}",
                        rating=5
                        if book.reading_status == BookReadingStatus.COMPLETED
                        else 4,
                        read_at=target_created_at,
                        weather=random.choice(["맑음", "흐림", "비"]),
                        created_at=target_created_at,
                    )
                    db.add(new_rec)
                    await db.flush()

                    rec_scrap = RecordScrap(
                        record_id=new_rec.id,
                        member_id=member_id,
                        book_id=book.id,
                        sentence=scrap_item["sentence"],
                        page_number=scrap_item["page_number"],
                        scrap_image_url=book.cover_url or "",
                        memo=scrap_item["memo"],
                        created_at=target_created_at,
                    )
                    db.add(rec_scrap)

        await db.commit()
        print("-> 16권 도서 및 줄거리 기반 스크랩 문장 적재 완료")

        # 6. 최근 독서 세션 36건 적재 (이번 달 [lo, hi] 범위 내 균등 추첨, 16권 전 도서 고른 분산, KST 시간대 정렬)
        # 기존 세션 삭제 후 36건 일관성 있게 새로 생성
        await db.execute(
            delete(ReadingSession).where(ReadingSession.member_id == member_id)
        )

        print(
            "-> 최근 독서 타이머 세션 로그 생성 중 (16권 전권 고른 분산 및 KST 시간대 정렬)..."
        )
        weathers = ["맑음", "맑음", "맑음", "흐림", "비"]
        kst_hours_pool = [5, 6, 10, 14, 16, 19, 20, 22, 23]

        lo = month_start_utc
        sessions_created = 0

        # 16권 전 도서에 최소 1~2건씩 배정하고 추가 추첨하여 36건 구성
        session_target_books = list(created_books) * 2 + [
            random.choice(created_books) for _ in range(4)
        ]
        random.shuffle(session_target_books)

        for target_book in session_target_books:
            hi = min(target_book.completed_at or now_utc, now_utc)

            if hi <= lo:
                continue

            duration_sec = random.randint(900, 3600)  # 15분 ~ 60분
            duration_min = duration_sec // 60

            # [lo, hi] 시간 창 안에서 균등하게 KST 시각을 추첨 (최대 50회 시도)
            for _ in range(50):
                random_fraction = random.random()
                sampled_dt = lo + (hi - lo) * random_fraction
                sampled_kst = sampled_dt.astimezone(SEOUL_TZ)

                chosen_hour = random.choice(kst_hours_pool)
                chosen_minute = random.randint(0, 45)

                start_kst = sampled_kst.replace(
                    hour=chosen_hour, minute=chosen_minute, second=0, microsecond=0
                )
                start_dt_utc = start_kst.astimezone(UTC)
                end_dt_utc = start_dt_utc + timedelta(seconds=duration_sec)

                if lo <= start_dt_utc and end_dt_utc <= hi:
                    break
            else:
                continue

            # 세션 페이지 분량 정합성 (도서 현재 진도 범위 고려)
            max_limit = target_book.current_page or target_book.total_pages or 200
            start_p = max(1, random.randint(1, max(1, max_limit - 20)))
            end_p = min(start_p + random.randint(10, 35), max_limit)

            session = ReadingSession(
                member_id=member_id,
                book_id=target_book.id,
                duration_seconds=duration_sec,
                duration_minutes=duration_min,
                start_time=start_dt_utc,
                end_time=end_dt_utc,
                start_page=start_p,
                end_page=end_p,
                weather=random.choice(weathers),
                memo=f"집중해서 읽음 ({target_book.title})",
                created_at=end_dt_utc,
            )
            db.add(session)
            sessions_created += 1

        await db.commit()
        print(
            f"-> 독서 세션 로그 {sessions_created}개 적재 완료 (16권 전 도서 분산 및 KST 시간대 정렬)!"
        )

        # 7. 사서와의 토론 통찰(Debate Insights) 페르소나 4종 풀세트 벡터 임베딩 및 적재
        print(
            "-> 사서와의 토론 통찰(Debate Insights) 페르소나 4종 5건 벡터 임베딩 및 적재 중..."
        )
        sample_debates = [
            {
                "book_title": "클린 코드 (Clean Code)",
                "topic": "기술 부채와 소프트웨어 장인정신",
                "persona_id": "debate_critic",
                "summary": "빠른 출시 압박 속에서도 코드 품질과 테스트를 타협하지 않는 원칙의 중요성을 논의함. 보이스카우트 규칙과 가독성 높은 네이밍이 장기적으로 시스템 유지보수 비용을 획기적으로 줄여준다는 결론에 도달함.",
            },
            {
                "book_title": "마흔에 읽는 쇼펜하우어",
                "topic": "인생의 결핍과 고통을 다루는 철학적 태도",
                "persona_id": "debate_counselor",
                "summary": "욕망과 권태 사이를 오가는 삶의 본질을 직시하고, 타인의 시선에서 벗어나 내면의 고독을 즐길 때 비로소 진정한 마음의 평온을 얻을 수 있다는 통찰을 나누며 깊은 위로를 받음.",
            },
            {
                "book_title": "파견자들",
                "topic": "포스트 아포칼립스 시대 미지의 생명체와 공존",
                "persona_id": "debate_storyteller",
                "summary": "지상 파견자들이 마주한 이질적인 진균류 생명체들과의 조우 과정을 분석함. 인간 중심적인 이분법적 사고를 탈피하여 낯선 존재와의 연결과 생태적 연대의 가능성을 깊이 있게 탐색함.",
            },
            {
                "book_title": "도둑맞은 집중력",
                "topic": "주의력 약탈 비즈니스 모델과 디지털 디톡스의 한계",
                "persona_id": "debate_observer",
                "summary": "개인의 절제력 부족이 아닌 빅테크 기업들의 중독 유도 알고리즘이 집중력 위기의 본질임을 파헤침. 개인적 차원의 스크린타임 관리를 넘어 사회적 연대와 규제 마련이 필수적이라는 거시적 통찰을 도출함.",
            },
            {
                "book_title": "사피엔스",
                "topic": "인간의 허구 창조 능력과 사회적 신뢰",
                "persona_id": "debate_critic",
                "summary": "화폐, 법률, 국가 등 인류 문명을 지탱하는 거대한 시스템들이 모두 집단적 상상력에 기반하고 있음을 분석하며, 현대의 인공지능 기술 역시 새로운 차원의 사회적 허구와 질서를 형성하고 있다는 점을 비평함.",
            },
        ]

        try:
            async with (
                db.begin_nested()
            ):  # SAVEPOINT: 실패해도 앞선 세션/도서 트랜잭션 오염 방지
                # 재실행 시 중복 적재 방지 (해당 데모 세션 삭제)
                await db.execute(
                    text(
                        "DELETE FROM agent.debate_insights "
                        "WHERE member_id = :mid AND session_id LIKE 'demo-session-%'"
                    ),
                    {"mid": member_id},
                )

                for d_item in sample_debates:
                    full_text = f"도서: {d_item['book_title']}\n논제: {d_item['topic']}\n토론 요약: {d_item['summary']}"
                    vec = generate_pseudo_embedding(full_text)
                    # pgvector 포맷 문자열
                    vec_str = "[" + ",".join(str(v) for v in vec) + "]"
                    d_id = uuid.uuid4()
                    sess_id = (
                        f"demo-session-{d_item['book_title']}-{d_item['persona_id']}"
                    )

                    await db.execute(
                        text(
                            """
                            INSERT INTO agent.debate_insights
                              (id, member_id, session_id, book_title, persona_id, summary, topic, embedding, created_at)
                            VALUES
                              (:id, :member_id, :session_id, :book_title, :persona_id, :summary, :topic, CAST(:embedding AS vector), :created_at)
                            """
                        ),
                        {
                            "id": d_id,
                            "member_id": member_id,
                            "session_id": sess_id,
                            "book_title": d_item["book_title"],
                            "persona_id": d_item["persona_id"],
                            "summary": d_item["summary"],
                            "topic": d_item["topic"],
                            "embedding": vec_str,
                            "created_at": month_start_utc
                            + timedelta(days=random.randint(2, 8)),
                        },
                    )
            await db.commit()
            print(
                "-> 토론 통찰(Debate Insights) 페르소나 4종 5건 적재 완료 (리포트 토론 키워드 추출 1순위 및 AI 개인화 완결)!"
            )
        except Exception as e:
            print(f"참고: agent.debate_insights 적재 건너뜀 ({e})")

        print(f"\n🎉 [{TARGET_EMAIL}] 데모 데이터 준비 완료!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="데모 계정 서재 시드 스크립트")
    parser.add_argument(
        "--yes", "-y", action="store_true", help="대상 DB 확인 프롬프트 자동 통과"
    )
    parser.add_argument(
        "--reset",
        "-r",
        action="store_true",
        help="회원의 기존 도서/스크랩/세션 전체 초기화 후 재적재",
    )
    args = parser.parse_args()

    asyncio.run(seed_demo_library(auto_yes=args.yes, reset_mode=args.reset))
