import re
from datetime import date
from typing import TYPE_CHECKING

from app.models.enums import GenreType

if TYPE_CHECKING:
    from app.core.ddc_mapper import (
        DDC_GENRE_MAPPING,
        ddc_to_genre,
        extract_ddc_code,
    )
    from app.core.genre_mapper import (
        GENRE_KOREAN_NAMES,
        LIGHTWEIGHT_FALLBACK_RULES,
        fallback_genre_by_keywords,
        parse_to_genre_and_subject,
    )

__all__ = [
    "GENRE_KOREAN_NAMES",
    "KDC_GENRE_MAPPING",
    "KDC_FIRST_CHAR_MAPPING",
    "extract_kdc_code",
    "kdc_to_genre",
    "kdc_to_subject",
    "DDC_GENRE_MAPPING",
    "extract_ddc_code",
    "ddc_to_genre",
    "LIGHTWEIGHT_FALLBACK_RULES",
    "fallback_genre_by_keywords",
    "parse_to_genre_and_subject",
    "parse_page_number",
    "parse_publish_date",
    "parse_to_date",
]

# ---------------------------------------------------------------------------
# KDC (한국십진분류법 제6판) 10대 대분류 매핑
# ---------------------------------------------------------------------------
# 000: 총류 (004/005 컴퓨터과학 포함)
# 100: 철학, 200: 종교, 300: 사회과학, 400: 자연과학, 500: 기술과학
# 600: 예술, 700: 언어, 800: 문학, 900: 역사
KDC_GENRE_MAPPING: dict[str, GenreType] = {
    "0": GenreType.GENERAL,
    "1": GenreType.PHILOSOPHY,
    "2": GenreType.RELIGION,
    "3": GenreType.SOCIAL_SCIENCE,
    "4": GenreType.NATURAL_SCIENCE,
    "5": GenreType.TECHNOLOGY,
    "6": GenreType.ARTS,
    "7": GenreType.LANGUAGE,
    "8": GenreType.LITERATURE,
    "9": GenreType.HISTORY,
}

# 100~900번대 KDC 첫째 자리 대분류 매핑 상수 (레거시 호환 룩업)
KDC_FIRST_CHAR_MAPPING = KDC_GENRE_MAPPING


def extract_kdc_code(kdc_str: str | None) -> str | None:
    """
    국립중앙도서관, 서지 데이터 및 청구기호 라벨에서 순수 KDC 분류기호(숫자)를 정밀 추출합니다.
    1. 도서관 청구기호 라벨 패턴: 'KDC 813.6', '320.1-박24ㄱ', 'K813.6-이38ㅅ'
    2. 5자리 ISBN 부가기호: '03320' -> 뒤 3자리 '320', '93810' -> '810'
    3. 표준 3자리 정수 + 선택적 소수점: '813.6', '005.133', '843'
    4. 접두사/약식 1~2자리 분류기호: '81', '00', '8', '0'
    """
    if not kdc_str or not kdc_str.strip():
        return None

    clean = kdc_str.strip()

    # 1. 도서관 청구기호 및 KDC 명시 접두사 라벨 패턴
    match_label = re.search(
        r"(?:(?:KDC|분류(?:기호)?)\s*:?\s*)?[A-Z]?(\d{3}(?:\.\d+)?)(?=[-\s/\[\(\]A-Za-z가-힣]|$)",
        clean,
        re.IGNORECASE,
    )
    if match_label:
        raw_match = match_label.group(1)
        start_idx, end_idx = match_label.span(1)
        is_embedded_in_longer_number = (
            start_idx > 0 and clean[start_idx - 1].isdigit()
        ) or (end_idx < len(clean) and clean[end_idx].isdigit())
        if not is_embedded_in_longer_number:
            return raw_match

    # 2. 5자리 ISBN 부가기호 처리 (예: '03320' -> '320', '93810' -> '810')
    match5 = re.search(r"(?:^|[^\d])\d{2}(\d{3})(?:[^\d]|$)", clean)
    if match5:
        return match5.group(1)

    # 3. 3자리 정수 + 선택적 소수점 (예: 813.6, 005.133, 843)
    match3 = re.search(r"(?:^|[^\d])(\d{3}(?:\.\d+)?)(?:[^\d]|$)", clean)
    if match3:
        return match3.group(1)

    # 4. 접두사/약식 1~2자리 (예: '81', '00', '8', '0')
    match_short = re.search(r"(?:^|[\s/\[\(])(\d{1,2}(?:\.\d+)?)(?:[\s/\]\)]|$)", clean)
    if match_short:
        return match_short.group(1)

    return None


def kdc_to_genre(kdc_str: str | None) -> GenreType:
    """
    순수 KDC(한국십진분류법 제6판) 분류기호를 10대 대분류 GenreType으로 변환합니다.
    - 000번대는 공식 KDC 표준에 따라 GENERAL(총류)로 매핑.
    - 분류기호가 없거나 유효하지 않으면 GenreType.NONE 반환.
    """
    code = extract_kdc_code(kdc_str)
    if not code:
        return GenreType.NONE

    first_char = code[0]
    return KDC_GENRE_MAPPING.get(first_char, GenreType.NONE)


def kdc_to_subject(kdc_str: str | None) -> str | None:
    """
    공식 분류기호로부터 대표 표준 주제어를 정규화 도출합니다.
    - KDC 004, 005 -> '컴퓨터/IT' (안 A 공식 대분류 GENERAL 보존 및 세부 주제 도출)
    - 800번대 주요 문학군 기본 구분 (813.7 SF, 814 에세이, 813 한국소설, 843 영미소설 등)
    """
    code = extract_kdc_code(kdc_str)
    if not code:
        return None

    # 컴퓨터과학/IT 세부 주제어 정규화 (안 A)
    if code.startswith(("004", "005")):
        return "컴퓨터/IT"

    # 800번대 대표 문학군
    if code.startswith("813.7"):
        return "SF/과학소설"
    if code.startswith(("814", "818")):
        return "에세이/산문"
    if code.startswith("813"):
        return "한국소설"
    if code.startswith("81"):
        return "한국문학"
    if code.startswith("843"):
        return "영미소설"
    if code.startswith("84"):
        return "영미문학"
    if code.startswith("833"):
        return "일본소설"
    if code.startswith("83"):
        return "일본문학"
    if code.startswith("823"):
        return "중국소설"
    if code.startswith("82"):
        return "중국문학"
    if code.startswith("8"):
        return "문학"

    return None


def parse_page_number(page_str: str | None) -> int | None:
    """국립중앙도서관 PAGE 필드에서 정수 페이지 번호만 추출 (예: '350p' -> 350)"""
    if not page_str:
        return None
    match = re.search(r"\d+", page_str)
    return int(match.group()) if match else None


def parse_publish_date(date_str: str | None) -> str | None:
    """
    국립중앙도서관 및 서지 데이터의 다양한 발행일자 형식을 유연하게 정규화.
    - 8자리 (YYYYMMDD): '20231225' -> '2023-12-25'
    - 8자리 중 월/일 미상 ('20230000'): '2023' (연도만 추출)
    - 6자리 (YYYYMM): '202312' -> '2023-12'
    - 4자리 (YYYY): '1998' -> '1998'
    """
    if not date_str:
        return None
    cleaned = re.sub(r"\D", "", date_str)
    length = len(cleaned)

    if length == 8:
        if cleaned[4:8] == "0000":
            return cleaned[:4]
        if cleaned[6:8] == "00":
            return f"{cleaned[:4]}-{cleaned[4:6]}"
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
    if length == 6:
        return f"{cleaned[:4]}-{cleaned[4:6]}"
    if length == 4:
        return cleaned[:4]

    return None


def parse_to_date(val: object) -> date | None:
    """
    다양한 서지 정보(국립중앙도서관, 알라딘, YES24 등)의 발행일자 형식을 파싱하여 datetime.date로 변환합니다.
    """
    if val is None:
        return None
    if isinstance(val, date):
        return val

    val_str = str(val).strip()
    if not val_str:
        return None

    cleaned = re.sub(r"\D", "", val_str)
    length = len(cleaned)

    try:
        if length >= 8:
            year = int(cleaned[:4])
            month = int(cleaned[4:6])
            day = int(cleaned[6:8])
            month = 1 if month < 1 or month > 12 else month
            day = 1 if day < 1 or day > 31 else day
            return date(year, month, day)
        elif length >= 6:
            year = int(cleaned[:4])
            month = int(cleaned[4:6])
            month = 1 if month < 1 or month > 12 else month
            return date(year, month, 1)
        elif length >= 4:
            year = int(cleaned[:4])
            return date(year, 1, 1)
    except (ValueError, TypeError):
        return None

    return None


def __getattr__(name: str) -> object:
    """레거시 임포트 하위 호환성을 위한 지연(Lazy) 해석 (PEP 562)"""
    if name in (
        "GENRE_KOREAN_NAMES",
        "LIGHTWEIGHT_FALLBACK_RULES",
        "fallback_genre_by_keywords",
        "parse_to_genre_and_subject",
    ):
        import app.core.genre_mapper as gm

        return getattr(gm, name)
    if name in ("DDC_GENRE_MAPPING", "ddc_to_genre", "extract_ddc_code"):
        import app.core.ddc_mapper as dm

        return getattr(dm, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
