from app.core.kdc_mapper import (
    GENRE_KOREAN_NAMES,
    kdc_to_genre,
    parse_page_number,
    parse_publish_date,
)
from app.models.enums import GenreType
from app.schemas.search import ExternalBook


def test_kdc_to_genre_mapping():
    assert kdc_to_genre("005.133") == GenreType.GENERAL
    assert kdc_to_genre("100") == GenreType.PHILOSOPHY
    assert kdc_to_genre("210") == GenreType.RELIGION
    assert kdc_to_genre("330") == GenreType.SOCIAL_SCIENCE
    assert kdc_to_genre("400") == GenreType.NATURAL_SCIENCE
    assert kdc_to_genre("590") == GenreType.TECHNOLOGY
    assert kdc_to_genre("600") == GenreType.ARTS
    assert kdc_to_genre("710") == GenreType.LANGUAGE
    assert kdc_to_genre("813.6") == GenreType.LITERATURE
    assert kdc_to_genre("900") == GenreType.HISTORY
    assert kdc_to_genre(None) == GenreType.NONE
    assert kdc_to_genre("") == GenreType.NONE
    assert kdc_to_genre("ABC") == GenreType.NONE


def test_genre_korean_names():
    assert GENRE_KOREAN_NAMES[GenreType.LITERATURE] == "문학"
    assert GENRE_KOREAN_NAMES[GenreType.TECHNOLOGY] == "기술과학"
    assert GENRE_KOREAN_NAMES[GenreType.NONE] == "기타/미분류"


def test_parse_page_number():
    assert parse_page_number("350p") == 350
    assert parse_page_number(" 412 쪽") == 412
    assert parse_page_number(None) is None
    assert parse_page_number("none") is None


def test_parse_publish_date():
    assert parse_publish_date("20231225") == "2023-12-25"
    assert parse_publish_date("2023-12-25") == "2023-12-25"
    assert parse_publish_date(None) is None
    assert parse_publish_date("123") is None


def test_external_book_computed_genre_name():
    book = ExternalBook(
        title="테스트 도서",
        author="저자",
        genre=GenreType.LITERATURE,
    )
    # Pydantic camelCase 직렬화 확인
    dump = book.model_dump(by_alias=True)
    assert dump["genre"] == "LITERATURE"
    assert dump["genreName"] == "문학"
