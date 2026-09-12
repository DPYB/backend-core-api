import re

from app.models.enums import GenreType

GENRE_KOREAN_NAMES = {
    GenreType.NONE: "기타/미분류",
    GenreType.GENERAL: "총류",
    GenreType.PHILOSOPHY: "철학",
    GenreType.RELIGION: "종교",
    GenreType.SOCIAL_SCIENCE: "사회과학",
    GenreType.NATURAL_SCIENCE: "자연과학",
    GenreType.TECHNOLOGY: "기술과학",
    GenreType.ARTS: "예술",
    GenreType.LANGUAGE: "언어",
    GenreType.LITERATURE: "문학",
    GenreType.HISTORY: "역사",
}


def kdc_to_genre(kdc_str: str | None) -> GenreType:
    """
    KDC 분류기호 문자열의 첫째 자리 숫자를 판별하여 10대 대분류 ENUM으로 변환.
    예: '813.6' -> LITERATURE, '005.133' -> GENERAL, '590' -> TECHNOLOGY
    """
    if not kdc_str or not kdc_str.strip():
        return GenreType.NONE

    first_char = kdc_str.strip()[0]
    mapping = {
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
    return mapping.get(first_char, GenreType.NONE)


def parse_page_number(page_str: str | None) -> int | None:
    """국립중앙도서관 PAGE 필드에서 정수 페이지 번호만 추출 (예: '350p' -> 350)"""
    if not page_str:
        return None
    match = re.search(r"\d+", page_str)
    return int(match.group()) if match else None


def parse_publish_date(date_str: str | None) -> str | None:
    """국립중앙도서관 PUBLISH_PREDATE (YYYYMMDD) 형식을 YYYY-MM-DD로 변환"""
    if not date_str:
        return None
    cleaned = re.sub(r"\D", "", date_str)
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
    return None
