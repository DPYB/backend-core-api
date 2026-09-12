import httpx

from app.config import settings
from app.core.exceptions import ExternalApiException
from app.core.kdc_mapper import (
    kdc_to_genre,
    parse_page_number,
    parse_publish_date,
)
from app.schemas.search import ExternalBook


class NationalLibraryClient:
    SEARCH_URL = "https://www.nl.go.kr/seoji/SearchApi.do"

    def __init__(self, cert_key: str | None = None):
        self.cert_key = cert_key or settings.NL_API_CERT_KEY or ""

    async def lookup_by_isbn(self, isbn: str) -> ExternalBook | None:
        """
        국립중앙도서관 서지정보 API를 호출하여 단건 도서 정보 조회.
        도서가 없으면 None 반환, API 오류 시 ExternalApiException 발생.
        """
        if not self.cert_key:
            # 인증키가 없을 때는 로컬 환경 테스트 등을 위해 빈 결과로 처리하거나 에러 발생 방지
            return None

        params = {
            "cert_key": self.cert_key,
            "result_style": "json",
            "page_no": 1,
            "page_size": 1,
            "isbn": isbn,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.SEARCH_URL, params=params)
                if resp.status_code != 200:
                    raise ExternalApiException(
                        f"국립중앙도서관 API HTTP 오류: {resp.status_code}"
                    )
                data = resp.json()
        except httpx.RequestError as e:
            raise ExternalApiException(f"국립중앙도서관 API 통신 실패: {str(e)}") from e
        except Exception as e:
            if isinstance(e, ExternalApiException):
                raise
            raise ExternalApiException(
                f"국립중앙도서관 API 응답 처리 중 오류: {str(e)}"
            ) from e

        # 에러코드 검사: 000(시스템오류), 010(인증키누락), 011(유효하지않은키), 015(필수파라미터누락)
        error_code = data.get("errorCode")
        if error_code:
            error_message = data.get("errorMessage", "알 수 없는 오류")
            raise ExternalApiException(
                f"국립중앙도서관 API 오류 [{error_code}]: {error_message}"
            )

        total_count = int(data.get("TOTAL_COUNT", 0))
        docs = data.get("docs", [])
        if total_count == 0 or not docs:
            return None

        item = docs[0]
        raw_kdc = item.get("KDC")
        raw_subject = item.get("SUBJECT")
        genre = kdc_to_genre(raw_kdc)

        return ExternalBook(
            title=item.get("TITLE", ""),
            author=item.get("AUTHOR", ""),
            isbn=item.get("EA_ISBN") or isbn,
            genre=genre,
            kdc=raw_kdc,
            subject=raw_subject,
            publisher=item.get("PUBLISHER"),
            published_date=parse_publish_date(item.get("PUBLISH_PREDATE")),
            total_pages=parse_page_number(item.get("PAGE")),
            cover_url=item.get("TITLE_URL"),
        )
