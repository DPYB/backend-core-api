import logging
import re
import time
from typing import Any

import httpx

from app.config import settings
from app.core.isbn import normalize_isbn
from app.core.kdc_mapper import parse_to_date
from app.schemas.search import BookSearchItem
from app.services.national_library import get_verified_cover_url

logger = logging.getLogger(__name__)


class Yes24Client:
    SEARCH_URL = "https://apis.yes24.com/v1/goods/itemList"
    DEFAULT_TTL_SECONDS = 900.0  # 인메모리 검색 캐시 TTL: 15분

    def __init__(self, api_key: str | None = None):
        self.api_key = (
            api_key or settings.YES_24_API_KEY or settings.YES24_API_KEY or ""
        ).strip()
        self._cache: dict[str, tuple[list[BookSearchItem], float]] = {}

    def clear_cache(self) -> None:
        """인메모리 캐시 초기화 (테스트 및 수동 갱신용)"""
        self._cache.clear()

    def _parse_book_item(self, it: dict[str, Any]) -> BookSearchItem | None:
        raw_isbn13 = (it.get("isbn13") or "").strip()
        raw_isbn10 = (it.get("isbn10") or "").strip()
        raw_isbn = (it.get("isbn") or "").strip()
        # 13자리 우선, 없으면 10자리 또는 일반 isbn 키 활용
        final_isbn = raw_isbn13 or raw_isbn10 or raw_isbn

        # 세트/번들 상품 등 ISBN 결측 상품 제외
        if not final_isbn:
            return None

        # 날짜 파싱
        pub_date_raw = it.get("publishDate")
        pub_date_str = None
        if pub_date_raw:
            parsed_d = parse_to_date(pub_date_raw)
            if parsed_d:
                pub_date_str = parsed_d.isoformat()

        # 표지 URL 및 교보문고 CDN 폴백
        raw_cover = it.get("cover")
        cover_url = get_verified_cover_url(raw_cover, final_isbn)
        side_cover_url = it.get("sideCover") or None

        # 소개글 추출
        content_detail = it.get("contentDetail") or {}
        description = content_detail.get("bookIntroduction") or content_detail.get(
            "bookSummary"
        )
        if description:
            description = description.strip()

        # 쪽수 파싱
        pages = None
        if it.get("pages") is not None:
            try:
                pages = int(it["pages"])
            except (ValueError, TypeError):
                pages = None

        # 평점 파싱
        star_score = None
        if it.get("starScore") is not None:
            try:
                star_score = float(it["starScore"])
            except (ValueError, TypeError):
                star_score = None

        # 상품 링크 파싱
        link = (
            it.get("link")
            or it.get("goodsUrl")
            or (
                f"https://www.yes24.com/Product/Goods/{it['goodsNo']}"
                if it.get("goodsNo")
                else None
            )
        )

        return BookSearchItem(
            title=it.get("title", "").strip(),
            author=it.get("author", "").strip(),
            isbn=final_isbn,
            publisher=(it.get("publisher") or "").strip() or None,
            published_date=pub_date_str,
            cover_url=cover_url,
            side_cover_url=side_cover_url,
            total_pages=pages,
            description=description,
            genre_source="KDC",
            link=link,
            is_registered=False,  # 라우터에서 회원 서재 대조 후 갱신
            star_score=star_score,
        )

    async def search_books(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> list[BookSearchItem]:
        """
        YES24 Open API를 호출하여 도서 키워드 검색 수행.
        - category="BOOK", detail="Y"를 적용하여 단행본 도서의 쪽수(pages), 앞표지(cover),
          책등(sideCover), 소개글(bookIntroduction), 평점(starScore), 상품링크(link)를 일괄 확보.
        - 세트/번들 등 ISBN 결측 상품은 제외(필터링).
        - 동일 ISBN 다중 상품은 In-memory Dedup (대표 상품 1건 유지).
        - 인메모리 TTL 캐시(15분) 적용으로 외부 API 호출 최소화.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. 인메모리 TTL 캐시 확인 (키: clean_query:page:page_size)
        cache_key = f"{clean_query}:{page}:{page_size}"
        now = time.time()
        if cache_key in self._cache:
            cached_items, expires_at = self._cache[cache_key]
            if now < expires_at:
                return cached_items
            del self._cache[cache_key]

        if not self.api_key:
            logger.warning("YES24_API_KEY가 설정되지 않아 외부 검색을 건너뜁니다.")
            return []

        params = {
            "query": clean_query,
            "category": "BOOK",
            "page": page,
            "pageSize": page_size,
            "detail": "Y",
        }
        headers = {
            "X-Api-Key": self.api_key,
            "User-Agent": "backend-core-api/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.SEARCH_URL, headers=headers, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        f"YES24 API HTTP 오류: {resp.status_code} (Query: {clean_query})"
                    )
                    return []
                data = resp.json()
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(
                f"YES24 API 통신 실패 또는 타임아웃: {e} (Query: {clean_query})"
            )
            return []
        except Exception as e:
            logger.warning(f"YES24 API 응답 처리 중 오류: {e} (Query: {clean_query})")
            return []

        if not data.get("success"):
            error_code = data.get("errorCode")
            message = data.get("message")
            logger.warning(
                f"YES24 API 비정상 응답 [{error_code}]: {message} (Query: {clean_query})"
            )
            return []

        raw_items = data.get("data", {}).get("items", [])
        items: list[BookSearchItem] = []
        seen_isbns: set[str] = set()

        for it in raw_items:
            item = self._parse_book_item(it)
            if not item:
                continue

            # 동일 ISBN Dedup (먼저 랭크된 대표 상품 1건 유지)
            if item.isbn in seen_isbns:
                continue
            seen_isbns.add(item.isbn)
            items.append(item)

        # 15분 캐시 저장
        self._cache[cache_key] = (items, now + self.DEFAULT_TTL_SECONDS)
        return items

    async def lookup_by_isbn(self, isbn: str) -> BookSearchItem | None:
        """
        YES24 Open API를 호출하여 단일 ISBN 기준 도서 상세 조회.
        - detail="Y" 파라미터 적용으로 소개글(bookIntroduction), 쪽수(pages), 앞표지(cover), 상품링크(link) 확보.
        - 인메모리 TTL 캐시(15분) 적용.
        """
        clean_isbn = re.sub(r"[-\s]", "", isbn.strip()).upper()
        if not clean_isbn:
            return None

        cache_key = f"isbn:{clean_isbn}"
        now = time.time()
        if cache_key in self._cache:
            cached_items, expires_at = self._cache[cache_key]
            if now < expires_at and cached_items:
                return cached_items[0]
            del self._cache[cache_key]

        if not self.api_key:
            logger.warning("YES24_API_KEY가 설정되지 않아 ISBN 조회를 건너뜁니다.")
            return None

        params = {
            "query": clean_isbn,
            "category": "BOOK",
            "page": 1,
            "pageSize": 5,
            "detail": "Y",
        }
        headers = {
            "X-Api-Key": self.api_key,
            "User-Agent": "backend-core-api/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.SEARCH_URL, headers=headers, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        f"YES24 lookup_by_isbn HTTP 오류: {resp.status_code} (ISBN: {clean_isbn})"
                    )
                    return None
                data = resp.json()
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(
                f"YES24 lookup_by_isbn 통신 실패 또는 타임아웃: {e} (ISBN: {clean_isbn})"
            )
            return None
        except Exception as e:
            logger.warning(
                f"YES24 lookup_by_isbn 처리 중 오류: {e} (ISBN: {clean_isbn})"
            )
            return None

        if not data.get("success"):
            return None

        norm_clean = None
        try:
            norm_clean = normalize_isbn(clean_isbn)
        except ValueError:
            pass

        raw_items = data.get("data", {}).get("items", [])
        for it in raw_items:
            item = self._parse_book_item(it)
            if not item:
                continue
            item_clean = re.sub(r"[-\s]", "", item.isbn).upper()
            norm_item = None
            try:
                norm_item = normalize_isbn(item_clean)
            except ValueError:
                pass

            is_match = (
                item_clean == clean_isbn
                or (
                    norm_clean is not None
                    and norm_item is not None
                    and norm_clean == norm_item
                )
                or (len(clean_isbn) >= 10 and clean_isbn in item_clean)
            )
            if is_match:
                self._cache[cache_key] = ([item], now + self.DEFAULT_TTL_SECONDS)
                return item

        return None

    @staticmethod
    def _clean_title_for_query(title: str) -> str:
        if not title:
            return ""
        # 콜론(:), 세미콜론(;), 등호(=) 앞의 주 표제어 추출
        cleaned = re.split(r"[:;=]", title)[0]
        # 괄호 및 괄호 내용 제거 (예: (양장본), [개정판])
        cleaned = re.sub(r"\(.*?\)|\[.*?\]", " ", cleaned)
        # 특수문자 제거 및 공백 정리
        cleaned = re.sub(r"[^\w\s가-힣a-zA-Z0-9]", " ", cleaned)
        return " ".join(cleaned.split())

    @staticmethod
    def _clean_author_for_query(author: str) -> str:
        if not author:
            return ""
        # 1) 첫 번째 저자 분리 (세미콜론, 슬래시, 콤마 등)
        first_author = re.split(r"[;/,]", author)[0].strip()
        # 2) 외곽 대괄호/소괄호 벗기기 (예: [지은이: 홍길동] -> 지은이: 홍길동)
        first_author = re.sub(r"^[\[\(]+|[\]\)]+$", "", first_author).strip()
        # 3) 접두어 제거 (지은이:, 저자:, 글:, 그림: 등)
        first_author = re.sub(r"^(?:지은이|저자|글|그림)\s*[:：]?\s*", "", first_author)
        # 4) 접미어 제거 (지음, 옮김, 저, 역, 편, 글, 그림, 외 등)
        first_author = re.sub(
            r"\s*(?:지음|옮김|저|역|편|글|그림|외)\b", "", first_author
        )
        # 5) 특수문자 제거 및 공백 정리
        first_author = re.sub(r"[^\w\s가-힣a-zA-Z]", " ", first_author)
        return " ".join(first_author.split())

    async def lookup_by_title_and_author(
        self,
        title: str,
        author: str,
        clean_isbn: str,
    ) -> BookSearchItem | None:
        """
        국립중앙도서관 결과의 제목·저자를 활용하여 YES24에서 2차 보완 검색 수행.
        - 1차 ISBN 검색 실패 시 호출되는 안전 폴백.
        - 원본 title, author는 보존하고, 검색용 정제어만 생성하여 질의.
        - 후보 도서들의 ISBN을 정규화하여 요청된 clean_isbn과 엄격히 일치하는 경우에만 채택 (다른 판본/오매칭 차단).
        - 응답 지연 방지를 위해 단축 타임아웃(3.0초) 및 15분 인메모리 TTL 캐시 적용.
        """
        norm_target_isbn = None
        try:
            norm_target_isbn = normalize_isbn(clean_isbn)
        except ValueError:
            pass

        if not norm_target_isbn:
            return None

        clean_title = self._clean_title_for_query(title)
        clean_author = self._clean_author_for_query(author)
        if not clean_title:
            return None

        query_str = f"{clean_title} {clean_author}".strip()
        cache_key = f"fallback:{norm_target_isbn}:{query_str}"
        now = time.time()
        if cache_key in self._cache:
            cached_items, expires_at = self._cache[cache_key]
            if now < expires_at and cached_items:
                return cached_items[0]
            del self._cache[cache_key]

        if not self.api_key:
            return None

        params = {
            "query": query_str,
            "category": "BOOK",
            "page": 1,
            "pageSize": 5,
            "detail": "Y",
        }
        headers = {
            "X-Api-Key": self.api_key,
            "User-Agent": "backend-core-api/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(self.SEARCH_URL, headers=headers, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        f"YES24 lookup_by_title_and_author HTTP 오류: {resp.status_code} (Query: {query_str})"
                    )
                    return None
                data = resp.json()
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(
                f"YES24 lookup_by_title_and_author 통신 실패 또는 타임아웃: {e} (Query: {query_str})"
            )
            return None
        except Exception as e:
            logger.warning(
                f"YES24 lookup_by_title_and_author 처리 중 오류: {e} (Query: {query_str})"
            )
            return None

        if not data.get("success"):
            return None

        raw_items = data.get("data", {}).get("items", [])
        for it in raw_items:
            item = self._parse_book_item(it)
            if not item:
                continue

            item_clean_isbn = re.sub(r"[-\s]", "", item.isbn).upper()
            norm_candidate_isbn = None
            try:
                norm_candidate_isbn = normalize_isbn(item_clean_isbn)
            except ValueError:
                pass

            # 조건 3 & 5 준수: 정규화된 13자리 ISBN이 정확히 일치하는 경우에만 동일 도서로 인정
            if norm_candidate_isbn and norm_candidate_isbn == norm_target_isbn:
                # 저자 정보가 둘 다 존재할 경우, 대표 저자명이 불일치하면 기각 (동명 이서 방어)
                if clean_author and item.author:
                    cand_author = self._clean_author_for_query(item.author)
                    if (
                        cand_author
                        and cand_author not in clean_author
                        and clean_author not in cand_author
                    ):
                        logger.warning(
                            f"YES24 후보 도서 저자 불일치: 요청={clean_author}, 후보={cand_author} (ISBN: {clean_isbn})"
                        )
                        continue

                self._cache[cache_key] = ([item], now + self.DEFAULT_TTL_SECONDS)
                return item

        return None
