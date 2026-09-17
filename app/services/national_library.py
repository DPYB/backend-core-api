import logging
import re
import time

import httpx

from app.config import settings
from app.core.kdc_mapper import (
    kdc_to_genre,
    kdc_to_subject,
    parse_page_number,
    parse_publish_date,
    refine_subject_by_keywords,
)
from app.schemas.search import ExternalBook

logger = logging.getLogger(__name__)


def get_verified_cover_url(cover_url: str | None, isbn: str | None) -> str | None:
    """
    도서 표지 이미지 URL 검증 및 교보문고 고화질 CDN 0ms 즉시 폴백.
    1. 국립중앙도서관 공식 표지 URL이 존재하면 우선 사용.
    2. 누락된 경우 10자리/13자리 정제된 ISBN을 기반으로 교보문고 CDN 이미지 URL 자동 생성.
    """
    clean_url = (cover_url or "").strip()
    if clean_url and clean_url.startswith(("http://", "https://")):
        return clean_url

    clean_isbn = re.sub(r"[^0-9X]", "", (isbn or "").strip())
    if clean_isbn and len(clean_isbn) in (10, 13):
        return f"https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/{clean_isbn}.jpg"

    return None


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
        - 국립중앙도서관 표지 누락 시 교보문고 고화질 CDN으로 즉시 폴백.
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

        # 세부 주제(SF, 에세이, 소설, IT 등) 우선 추출 (없을 시 비숫자 raw_subject 활용)
        inferred_subject = kdc_to_subject(raw_kdc)
        if (
            not inferred_subject
            and raw_subject
            and not str(raw_subject).strip().isdigit()
        ):
            inferred_subject = str(raw_subject).strip()

        # 외국 SF 소설 등 KDC 800번대 한계 보완: 도서 제목 및 부가정보 기반 SF 오버라이드
        title = item.get("TITLE", "")
        raw_description = item.get("DESCRIPTION") or (
            str(raw_subject)
            if raw_subject and not str(raw_subject).strip().isdigit()
            else None
        )
        inferred_subject = refine_subject_by_keywords(
            title=title,
            subject=inferred_subject,
            description=raw_description,
        )

        final_isbn = item.get("EA_ISBN") or clean_isbn
        cover_url = get_verified_cover_url(item.get("TITLE_URL"), final_isbn)

        external_book = ExternalBook(
            title=item.get("TITLE", ""),
            author=item.get("AUTHOR", ""),
            isbn=final_isbn,
            genre=genre,
            kdc=raw_kdc,
            subject=inferred_subject,
            publisher=item.get("PUBLISHER"),
            published_date=parse_publish_date(item.get("PUBLISH_PREDATE")),
            total_pages=parse_page_number(item.get("PAGE")),
            cover_url=cover_url,
        )

        # 성공 도서 캐싱
        self._cache[clean_isbn] = (external_book, now + self.DEFAULT_TTL_SECONDS)
        return external_book
