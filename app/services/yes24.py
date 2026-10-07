import logging
import time

import httpx

from app.config import settings
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

    async def search_books(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> list[BookSearchItem]:
        """
        YES24 Open API를 호출하여 도서 키워드 검색 수행.
        - category="BOOK", detail="Y"를 적용하여 단행본 도서의 쪽수(pages), 앞표지(cover),
          책등(sideCover), 소개글(bookIntroduction), 평점(starScore)을 일괄 확보.
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
            raw_isbn13 = (it.get("isbn13") or "").strip()
            raw_isbn10 = (it.get("isbn10") or "").strip()
            # 13자리 우선, 없으면 10자리 활용
            final_isbn = raw_isbn13 or raw_isbn10

            # 세트/번들 상품 등 ISBN 결측 상품 제외
            if not final_isbn:
                continue

            # 동일 ISBN Dedup (먼저 랭크된 대표 상품 1건 유지)
            if final_isbn in seen_isbns:
                continue
            seen_isbns.add(final_isbn)

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

            item = BookSearchItem(
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
                is_registered=False,  # 라우터에서 회원 서재 대조 후 갱신
                star_score=star_score,
            )
            items.append(item)

        # 15분 캐시 저장
        self._cache[cache_key] = (items, now + self.DEFAULT_TTL_SECONDS)
        return items
