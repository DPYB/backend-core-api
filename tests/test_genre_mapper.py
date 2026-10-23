from app.core.genre_mapper import (
    GENRE_KOREAN_NAMES,
    fallback_genre_by_keywords,
    parse_to_genre_and_subject,
)
from app.models.enums import GenreType


def test_genre_korean_names_completeness():
    for genre in GenreType:
        assert genre in GENRE_KOREAN_NAMES
        assert isinstance(GENRE_KOREAN_NAMES[genre], str)
        assert len(GENRE_KOREAN_NAMES[genre]) > 0


def test_fallback_genre_by_keywords():
    # 명확한 키워드 매핑
    assert fallback_genre_by_keywords("SF 소설 대모험") == (
        GenreType.LITERATURE,
        "SF/과학소설",
    )
    assert fallback_genre_by_keywords("어느 날의 에세이") == (
        GenreType.LITERATURE,
        "에세이",
    )
    assert fallback_genre_by_keywords("조선왕조실록 역사기행") == (
        GenreType.HISTORY,
        "역사",
    )
    assert fallback_genre_by_keywords("성경과 기도 생활") == (
        GenreType.RELIGION,
        "종교",
    )
    assert fallback_genre_by_keywords("실전 주식투자 재테크") == (
        GenreType.SOCIAL_SCIENCE,
        "경제/경영",
    )
    assert fallback_genre_by_keywords("파이썬 프로그래밍 시작하기") == (
        GenreType.GENERAL,
        "컴퓨터/IT",
    )

    # 모호하거나 지표어가 없으면 NONE 반환
    assert fallback_genre_by_keywords("그냥 평범한 이야기") == (
        GenreType.NONE,
        None,
    )
    assert fallback_genre_by_keywords(None) == (GenreType.NONE, None)
    assert fallback_genre_by_keywords("") == (GenreType.NONE, None)


def test_parse_to_genre_and_subject_catalog_priority():
    # 500번대: KDC는 기술과학, DDC는 자연과학
    # catalog="KR": KDC 우선
    genre_kr, sub_kr = parse_to_genre_and_subject(
        genre_input=None,
        kdc_str="500",
        ddc_str="500",
        catalog="KR",
    )
    assert genre_kr == GenreType.TECHNOLOGY

    # catalog="US": DDC 우선
    genre_us, sub_us = parse_to_genre_and_subject(
        genre_input=None,
        kdc_str="500",
        ddc_str="500",
        catalog="US",
    )
    assert genre_us == GenreType.NATURAL_SCIENCE


def test_parse_to_genre_and_subject_plan_a():
    # 안 A: KDC 004/005는 대분류 GENERAL, 세부주제 '컴퓨터/IT'
    genre, sub = parse_to_genre_and_subject(
        genre_input=None,
        kdc_str="004.1",
    )
    assert genre == GenreType.GENERAL
    assert sub == "컴퓨터/IT"


def test_parse_to_genre_and_subject_llm_subject_preservation():
    # 외부/LLM이 전달한 subject는 공식 분류와 상관없이 최우선 보존
    genre, sub = parse_to_genre_and_subject(
        genre_input="LITERATURE",
        current_subject="사이버펑크",
        kdc_str="813.7",
    )
    assert genre == GenreType.LITERATURE
    assert sub == "사이버펑크"
