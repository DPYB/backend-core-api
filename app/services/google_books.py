import logging
import os
import re
import time
from typing import Any

import httpx

from app.core.isbn import normalize_isbn
from app.core.kdc_mapper import parse_to_date
from app.models.enums import GenreType
from app.schemas.search import BookSearchItem, ExternalBook

logger = logging.getLogger(__name__)

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


class GoogleBooksClient:
    """Google Books API (v1) 연동 클라이언트.

    영문 및 글로벌 도서의 키워드 검색 및 ISBN 단건 상세 조회를 담당한다.
    - Rate limit (429), 네트워크 단절, 타임아웃, API 키 결측 시 안전하게 빈 결과를 반환하여 기존 검색 경로를 보호한다.
    - ISBN이 누락된 볼륨은 DTO 필수 필드 제약에 따라 후보에서 제외(Drop)한다.
    - 표지 이미지는 원본 HTTPS URL만 전달하며 로컬 영구 캐싱이나 저장을 수행하지 않는다.
    - Cache-Control 헤더 지시어(no-store, no-cache, max-age)를 준수하여 인메모리 캐싱을 수행한다.
    - ISBN 단건 조회 시 요청 ISBN과 응답 볼륨의 실제 ISBN 변환 일치 여부를 엄격히 대조한다.
    """

    VOLUMES_URL = "https://www.googleapis.com/books/v1/volumes"
    DEFAULT_TTL_SECONDS = 900.0  # 인메모리 검색 캐시 기본 TTL: 15분

    def __init__(self, api_key: str | None = None):
        self.api_key = (
            api_key if api_key is not None else os.getenv("GOOGLE_BOOKS_API_KEY", "")
        ).strip()
        self._cache: dict[str, tuple[list[BookSearchItem], float]] = {}

    def clear_cache(self) -> None:
        """인메모리 캐시 초기화 (테스트 및 수동 갱신용)"""
        self._cache.clear()

    def _clean_html(self, text: str | None) -> str | None:
        if not text:
            return None
        cleaned = HTML_TAG_PATTERN.sub("", text).strip()
        return cleaned or None

    def _parse_cache_control(
        self, cache_control_header: str | None
    ) -> tuple[bool, float]:
        """Cache-Control 헤더를 파싱하여 (캐싱 허용 여부, TTL 초)를 반환한다.

        - no-store 또는 no-cache 지시어가 포함된 경우 캐싱 불허 (False, 0.0)
        - max-age=N이 있으면 min(N, DEFAULT_TTL_SECONDS) 적용 (0 이하면 캐싱 불허)
        - 지시어가 없으면 기본 TTL (True, DEFAULT_TTL_SECONDS) 적용
        """
        if not cache_control_header:
            return True, self.DEFAULT_TTL_SECONDS

        header_lower = cache_control_header.lower()
        directives = [d.strip() for d in header_lower.split(",")]

        if any(d in directives for d in ("no-store", "no-cache")):
            return False, 0.0

        for d in directives:
            if d.startswith("max-age="):
                try:
                    max_age_val = float(d.split("=", 1)[1].strip())
                    if max_age_val <= 0:
                        return False, 0.0
                    return True, min(max_age_val, self.DEFAULT_TTL_SECONDS)
                except (ValueError, IndexError):
                    pass

        return True, self.DEFAULT_TTL_SECONDS

    def _parse_volume(self, item_data: dict[str, Any]) -> BookSearchItem | None:
        vol = item_data.get("volumeInfo") or {}
        title = (vol.get("title") or "").strip()
        if not title:
            return None

        # 저자 파싱
        authors = vol.get("authors") or []
        author = ", ".join(str(a) for a in authors).strip() or "저자 미상"

        # ISBN 추출 (ISBN_13 우선, 없으면 ISBN_10)
        identifiers = vol.get("industryIdentifiers") or []
        isbn_13: str | None = None
        isbn_10: str | None = None
        for ident in identifiers:
            id_type = ident.get("type", "")
            id_val = (ident.get("identifier") or "").replace("-", "").strip()
            if id_type == "ISBN_13" and len(id_val) == 13:
                isbn_13 = id_val
            elif id_type == "ISBN_10" and len(id_val) == 10:
                isbn_10 = id_val

        final_isbn = isbn_13 or isbn_10
        # 스키마(BookSearchItem.isbn: str) 필수 제약 준수: ISBN 결측 항목은 제외
        if not final_isbn:
            return None

        # 출판일 파싱
        pub_date_raw = vol.get("publishedDate")
        pub_date_str = None
        if pub_date_raw:
            parsed_d = parse_to_date(str(pub_date_raw))
            if parsed_d:
                pub_date_str = parsed_d.isoformat()
            else:
                pub_date_str = str(pub_date_raw).strip() or None

        # 표지 URL (HTTPS 강제 변환)
        image_links = vol.get("imageLinks") or {}
        raw_cover = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        cover_url: str | None = None
        if raw_cover:
            cover_url = raw_cover.replace("http://", "https://")

        # 쪽수 파싱
        total_pages: int | None = None
        if vol.get("pageCount") is not None:
            try:
                total_pages = int(vol["pageCount"])
            except (ValueError, TypeError):
                total_pages = None

        # 평점 파싱
        star_score: float | None = None
        if vol.get("averageRating") is not None:
            try:
                star_score = float(vol["averageRating"])
            except (ValueError, TypeError):
                star_score = None

        # 줄거리 소개글 정제
        raw_desc = vol.get("description")
        description = self._clean_html(raw_desc)

        # 링크
        link = vol.get("infoLink")

        return BookSearchItem(
            title=title,
            author=author,
            isbn=final_isbn,
            publisher=(vol.get("publisher") or "").strip() or None,
            published_date=pub_date_str,
            cover_url=cover_url,
            side_cover_url=None,
            total_pages=total_pages,
            description=description,
            genre_source="GOOGLE",
            genre_confidence=None,
            link=link,
            is_registered=False,
            star_score=star_score,
            data_source="GOOGLE",
        )

    async def search_books(
        self,
        query: str,
        limit: int = 10,
        timeout: float = 2.0,
    ) -> list[BookSearchItem]:
        """Google Books 키워드 검색 수행.

        - YES24 미검색/0건 시 2차 폴백 경로로 호출된다.
        - 시간 초과 방지를 위해 호출부에서 전달된 동적 타임아웃 예산(timeout)을 엄격히 준수한다.
        - 오류 유형(키 누락, 429, 타임아웃, 네트워크 단절)과 정상 0건 결과를 내부 로그에서 명확히 구분한다.
        - Cache-Control 헤더(no-store, no-cache, max-age) 지시어를 검증하여 캐싱을 수행한다.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. 인메모리 TTL 캐시 확인
        cache_key = f"{clean_query}:{limit}"
        now = time.time()
        if cache_key in self._cache:
            cached_items, expires_at = self._cache[cache_key]
            if now < expires_at:
                return cached_items
            del self._cache[cache_key]

        # 2. API 키 누락 시 안전 종료 및 로그 구분
        if not self.api_key:
            logger.warning(
                "GOOGLE_BOOKS_API_KEY 미설정으로 Google Books 검색을 건너뜁니다 [REASON=KEY_MISSING]"
            )
            return []

        params: dict[str, Any] = {
            "q": clean_query,
            "maxResults": min(max(limit, 1), 40),
            "printType": "books",
            "projection": "full",
            "key": self.api_key,
        }
        headers = {"User-Agent": "backend-core-api/1.0"}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    self.VOLUMES_URL, headers=headers, params=params
                )
                if resp.status_code == 429:
                    logger.warning(
                        "Google Books API 호출 한도 초과 [REASON=RATE_LIMIT_429]"
                    )
                    return []
                if resp.status_code != 200:
                    logger.warning(
                        f"Google Books API HTTP 오류 [{resp.status_code}] [REASON=HTTP_ERROR]"
                    )
                    return []
                data = resp.json()
        except httpx.TimeoutException:
            logger.warning(
                f"Google Books API 타임아웃 ({timeout}s 초과) [REASON=TIMEOUT]"
            )
            return []
        except httpx.RequestError as e:
            logger.warning(
                f"Google Books API 네트워크 연결 오류: {e} [REASON=NETWORK_ERROR]"
            )
            return []

        # 3. Cache-Control 헤더 검증
        cc_header = resp.headers.get("Cache-Control")
        is_cacheable, ttl_seconds = self._parse_cache_control(cc_header)

        raw_items = data.get("items") or []
        total_items = data.get("totalItems", 0)

        # 정상 0건 결과 식별
        if not raw_items or total_items == 0:
            logger.info(
                f"Google Books API 검색 결과 0건 [REASON=EMPTY_RESULT] (Query: {clean_query})"
            )
            if is_cacheable:
                self._cache[cache_key] = ([], now + ttl_seconds)
            return []

        items: list[BookSearchItem] = []
        seen_isbns: set[str] = set()

        for it in raw_items:
            parsed = self._parse_volume(it)
            if parsed and parsed.isbn not in seen_isbns:
                seen_isbns.add(parsed.isbn)
                items.append(parsed)
                if len(items) >= limit:
                    break

        if is_cacheable:
            self._cache[cache_key] = (items, now + ttl_seconds)
        return items

    async def lookup_by_isbn(
        self,
        clean_isbn: str,
        timeout: float = 2.0,
    ) -> ExternalBook | None:
        """ISBN 단건 검색을 통해 ExternalBook 서지정보를 반환한다.

        - 기존 YES24 및 국립중앙도서관이 모두 유효 서지정보를 확보하지 못했을 때 최종 보완 경로로만 호출된다.
        - 요청 ISBN의 체크섬 및 유효성을 검증하고, Google Books 응답 볼륨에 실제 포함된 ISBN(ISBN-10/13 상호 변환 포함)과
          엄격히 대조하여 일치하는 경우에만 반환한다. 불일치/누락 시 요청 ISBN을 임의 주입하지 않고 None을 반환한다.
        """
        # 1. 요청 ISBN 체크섬 및 유효성 검증 (정규화된 13자리 기준값 도출)
        try:
            norm_req_isbn = normalize_isbn(clean_isbn)
        except ValueError:
            logger.warning(
                f"유효하지 않은 요청 ISBN 형식/체크섬으로 Google Books 조회를 건너뜁니다 [ISBN: {clean_isbn}]"
            )
            return None

        if not norm_req_isbn:
            return None

        if not self.api_key:
            logger.warning(
                "GOOGLE_BOOKS_API_KEY 미설정으로 Google Books ISBN 조회를 건너뜁니다 [REASON=KEY_MISSING]"
            )
            return None

        params = {
            "q": f"isbn:{norm_req_isbn}",
            "maxResults": 1,
            "key": self.api_key,
        }
        headers = {"User-Agent": "backend-core-api/1.0"}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    self.VOLUMES_URL, headers=headers, params=params
                )
                if resp.status_code == 429:
                    logger.warning(
                        "Google Books API ISBN 조회 한도 초과 [REASON=RATE_LIMIT_429]"
                    )
                    return None
                if resp.status_code != 200:
                    logger.warning(
                        f"Google Books API ISBN 조회 HTTP 오류 [{resp.status_code}] [REASON=HTTP_ERROR]"
                    )
                    return None
                data = resp.json()
        except httpx.TimeoutException:
            logger.warning(
                f"Google Books API ISBN 조회 타임아웃 ({timeout}s 초과) [REASON=TIMEOUT]"
            )
            return None
        except httpx.RequestError as e:
            logger.warning(
                f"Google Books API ISBN 조회 네트워크 연결 오류: {e} [REASON=NETWORK_ERROR]"
            )
            return None

        raw_items = data.get("items") or []
        if not raw_items:
            logger.info(
                f"Google Books API ISBN 검색 결과 없음 [REASON=EMPTY_RESULT] (ISBN: {norm_req_isbn})"
            )
            return None

        volume_data = raw_items[0]
        vol = volume_data.get("volumeInfo") or {}

        # 2. 응답 볼륨 내 실제 포함된 모든 ISBN 추출 및 정규화
        identifiers = vol.get("industryIdentifiers") or []
        volume_norm_isbns: set[str] = set()
        for ident in identifiers:
            raw_id = (ident.get("identifier") or "").replace("-", "").strip()
            try:
                norm_id = normalize_isbn(raw_id)
                if norm_id:
                    volume_norm_isbns.add(norm_id)
            except ValueError:
                continue

        # 3. 요청 ISBN과 응답 볼륨의 ISBN 엄격 대조 (불일치 또는 누락 시 서지 오염 방지를 위해 차단)
        if norm_req_isbn not in volume_norm_isbns:
            logger.warning(
                f"Google Books 응답 도서의 ISBN이 요청 ISBN과 불일치하여 제외합니다 "
                f"[REQ: {norm_req_isbn}, FOUND: {volume_norm_isbns}]"
            )
            return None

        parsed_item = self._parse_volume(volume_data)
        if not parsed_item:
            return None

        return ExternalBook(
            title=parsed_item.title,
            author=parsed_item.author,
            isbn=parsed_item.isbn,
            genre=GenreType.NONE,
            kdc=None,
            subject=None,
            publisher=parsed_item.publisher,
            published_date=parsed_item.published_date,
            total_pages=parsed_item.total_pages,
            cover_url=parsed_item.cover_url,
            side_cover_url=None,
            description=parsed_item.description,
            genre_source="GOOGLE",
            genre_confidence=None,
            link=parsed_item.link,
        )
