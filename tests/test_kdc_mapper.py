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
    assert dump["displayGenre"] == "문학"


def test_kdc_to_subject_mapping():
    from app.core.kdc_mapper import kdc_to_subject

    assert kdc_to_subject("813.7") == "SF/과학소설"
    assert kdc_to_subject("814") == "에세이/산문"
    assert kdc_to_subject("818") == "에세이/산문"
    assert kdc_to_subject("813.6") == "한국소설"
    assert kdc_to_subject("823") == "영미소설"
    assert kdc_to_subject("893.3") == "일본문학"
    assert kdc_to_subject("005.133") == "IT/프로그래밍"
    assert kdc_to_subject("189") == "심리학"
    assert kdc_to_subject("320") == "경제/경영"
    assert kdc_to_subject("510") == "건강/의학"
    assert kdc_to_subject("980") == "여행/지리"
    assert kdc_to_subject(None) is None
    assert kdc_to_subject("") is None


def test_parse_to_genre_and_subject():
    from app.core.kdc_mapper import parse_to_genre_and_subject

    # 1. 국문 키워드 입력
    genre, sub = parse_to_genre_and_subject("SF")
    assert genre == GenreType.LITERATURE
    assert sub == "SF"

    genre, sub = parse_to_genre_and_subject("에세이")
    assert genre == GenreType.LITERATURE
    assert sub == "에세이"

    genre, sub = parse_to_genre_and_subject("인문/철학")
    assert genre == GenreType.PHILOSOPHY
    assert sub == "인문/철학"

    genre, sub = parse_to_genre_and_subject("IT/컴퓨터")
    assert genre == GenreType.TECHNOLOGY
    assert sub == "IT/컴퓨터"

    # 2. 영문 / 레거시 키워드 입력
    genre, sub = parse_to_genre_and_subject("literature")
    assert genre == GenreType.LITERATURE

    genre, sub = parse_to_genre_and_subject("SCIENCE_FICTION")
    assert genre == GenreType.LITERATURE
    assert sub == "SF"

    genre, sub = parse_to_genre_and_subject("self_help")
    assert genre == GenreType.PHILOSOPHY
    assert sub == "자기계발"

    # 3. KDC 분류기호 입력
    genre, sub = parse_to_genre_and_subject("813.7")
    assert genre == GenreType.LITERATURE
    assert sub == "SF/과학소설"

    # 4. 기존 subject 보존
    genre, sub = parse_to_genre_and_subject("LITERATURE", current_subject="우주 SF")
    assert genre == GenreType.LITERATURE
    assert sub == "우주 SF"

    # 5. 알 수 없는 사용자 지정 텍스트
    genre, sub = parse_to_genre_and_subject("신비한우주탐험")
    assert genre == GenreType.NONE
    assert sub == "신비한우주탐험"


def test_display_genre_prefers_subject_over_genre_name():
    # subject가 있으면 displayGenre는 subject
    book_with_sub = ExternalBook(
        title="우리가 빛의 속도로 갈 수 없다면",
        author="김초엽",
        genre=GenreType.LITERATURE,
        subject="SF/과학소설",
    )
    dump1 = book_with_sub.model_dump(by_alias=True)
    assert dump1["displayGenre"] == "SF/과학소설"

    # subject가 없으면 displayGenre는 genreName ("문학")
    book_without_sub = ExternalBook(
        title="일반 문학책",
        author="작가",
        genre=GenreType.LITERATURE,
        subject=None,
    )
    dump2 = book_without_sub.model_dump(by_alias=True)
    assert dump2["displayGenre"] == "문학"
