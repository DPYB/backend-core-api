import logging
import time

import httpx

from app.config import settings
from app.core.kdc_mapper import (
    kdc_to_genre,
    parse_page_number,
    parse_publish_date,
)
from app.schemas.search import ExternalBook

logger = logging.getLogger(__name__)


class NationalLibraryClient:
    SEARCH_URL = "https://www.nl.go.kr/seoji/SearchApi.do"
    DEFAULT_TTL_SECONDS = 86400.0  # 정상 도서 캐시 TTL: 24시간
    NEGATIVE_TTL_SECONDS = 3600.0  # 미존재 도서 캐시 TTL: 1시간

    def __init__(self, cert_key: str | None = None):
        self.cert_key = cert_key or settings.NL_API_CERT_KEY or ""
        self._cache: dict[str, tuple[ExternalBook | None, float]] = {}

    def clear_cache(self) -> None:
        """인메모리 캐시 전체 초기화 (테스트 및 수동 갱신용)"""
        self._cache.clear()

    async def lookup_by_isbn(self, isbn: str) -> ExternalBook | None:
        """
        국립중앙도서관 서지정보 API를 호출하여 단건 도서 정보 조회.
        - 동일 ISBN 중복 조회 시 인메모리 TTL 캐시 우선 반환.
        - 도서 미존재 또는 외부 API 일시 장애/타임아웃 발생 시 Graceful Fallback (None 반환).
        """
        clean_isbn = isbn.strip()

        # 1. 인메모리 TTL 캐시 조회
        now = time.time()
        if clean_isbn in self._cache:
            cached_book, expires_at = self._cache[clean_isbn]
            if now < expires_at:
                return cached_book
            del self._cache[clean_isbn]

        if not self.cert_key:
            # 인증키가 없을 때는 로컬 환경 테스트 등을 위해 빈 결과로 처리
            return None

        params = {
            "cert_key": self.cert_key,
            "result_style": "json",
            "page_no": 1,
            "page_size": 1,
            "isbn": clean_isbn,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.SEARCH_URL, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        f"국립중앙도서관 API HTTP 오류: {resp.status_code} (ISBN: {clean_isbn})"
                    )
                    return None
                data = resp.json()
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning(
                f"국립중앙도서관 API 통신 타임아웃 또는 실패: {e} (ISBN: {clean_isbn})"
            )
            return None
        except Exception as e:
            logger.warning(
                f"국립중앙도서관 API 응답 처리 중 오류: {e} (ISBN: {clean_isbn})"
            )
            return None

        # 에러코드 검사: 000(시스템오류), 010(인증키누락), 011(유효하지않은키), 015(필수파라미터누락)
        error_code = data.get("errorCode")
        if error_code:
            error_message = data.get("errorMessage", "알 수 없는 오류")
            logger.warning(
                f"국립중앙도서관 API 오류 응답 [{error_code}]: {error_message} (ISBN: {clean_isbn})"
            )
            return None

        total_count = int(data.get("TOTAL_COUNT", 0))
        docs = data.get("docs", [])
        if total_count == 0 or not docs:
            # Negative Caching (미존재 도서도 1시간 캐싱하여 외부 부하 경감)
            self._cache[clean_isbn] = (None, now + self.NEGATIVE_TTL_SECONDS)
            return None

        item = docs[0]
        raw_kdc = item.get("KDC")
        raw_subject = item.get("SUBJECT")
        genre = kdc_to_genre(raw_kdc)

        external_book = ExternalBook(
            title=item.get("TITLE", ""),
            author=item.get("AUTHOR", ""),
            isbn=item.get("EA_ISBN") or clean_isbn,
            genre=genre,
            kdc=raw_kdc,
            subject=raw_subject,
            publisher=item.get("PUBLISHER"),
            published_date=parse_publish_date(item.get("PUBLISH_PREDATE")),
            total_pages=parse_page_number(item.get("PAGE")),
            cover_url=item.get("TITLE_URL"),
        )

        # 성공 도서 캐싱
        self._cache[clean_isbn] = (external_book, now + self.DEFAULT_TTL_SECONDS)
        return external_book
