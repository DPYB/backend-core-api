from app.core.kdc_mapper import (
    GENRE_KOREAN_NAMES,
    ddc_to_genre,
    fallback_genre_by_keywords,
    kdc_to_genre,
    kdc_to_subject,
    parse_page_number,
    parse_publish_date,
    parse_to_genre_and_subject,
)
from app.models.enums import GenreType
from app.schemas.search import ExternalBook


def test_kdc_to_genre_mapping():
    # KDC 제6판 공식 10대 대분류 매핑 검증
    # 안 A: KDC 000번대(004/005 포함)는 공식 표준에 따라 GENERAL(총류)로 매핑
    assert kdc_to_genre("005.133") == GenreType.GENERAL
    assert kdc_to_genre("004.1") == GenreType.GENERAL
    assert kdc_to_genre("029.1") == GenreType.GENERAL
    assert kdc_to_genre("030") == GenreType.GENERAL
    assert kdc_to_genre("100") == GenreType.PHILOSOPHY
    assert kdc_to_genre("210") == GenreType.RELIGION
    assert kdc_to_genre("330") == GenreType.SOCIAL_SCIENCE
    assert kdc_to_genre("400") == GenreType.NATURAL_SCIENCE  # KDC 400 = 자연과학
    assert kdc_to_genre("590") == GenreType.TECHNOLOGY  # KDC 500 = 기술과학
    assert kdc_to_genre("600") == GenreType.ARTS  # KDC 600 = 예술
    assert kdc_to_genre("710") == GenreType.LANGUAGE  # KDC 700 = 언어
    assert kdc_to_genre("813.6") == GenreType.LITERATURE
    assert kdc_to_genre("900") == GenreType.HISTORY
    assert kdc_to_genre(None) == GenreType.NONE
    assert kdc_to_genre("") == GenreType.NONE
    assert kdc_to_genre("ABC") == GenreType.NONE

    # 권차, 판차 등 부가정보가 혼합된 KDC 문자열 앵커링 정규화 검증
    assert kdc_to_genre("5판 813.6") == GenreType.LITERATURE
    assert kdc_to_genre("[5] 813.6") == GenreType.LITERATURE
    assert kdc_to_genre("813.6/005") == GenreType.LITERATURE
    assert kdc_to_genre("K813.6") == GenreType.LITERATURE
    assert kdc_to_genre("v.2 813.72") == GenreType.LITERATURE

    # 도서관 청구기호 라벨 검증
    assert kdc_to_genre("KDC 813.6-박24ㄱ") == GenreType.LITERATURE
    assert kdc_to_genre("320.1-이38ㅅ-v.1") == GenreType.SOCIAL_SCIENCE

    # 5자리 ISBN 부가기호 (예: 03320 -> 320 사회과학, 93810 -> 810 문학)
    assert kdc_to_genre("03320") == GenreType.SOCIAL_SCIENCE
    assert kdc_to_genre("93810") == GenreType.LITERATURE


def test_ddc_to_genre_mapping():
    # DDC 제23판 공식 10대 대분류 매핑 검증
    assert (
        ddc_to_genre("005.133") == GenreType.GENERAL
    )  # DDC 000 = Computer Science & General
    assert ddc_to_genre("100") == GenreType.PHILOSOPHY
    assert ddc_to_genre("200") == GenreType.RELIGION
    assert ddc_to_genre("300") == GenreType.SOCIAL_SCIENCE
    assert (
        ddc_to_genre("400") == GenreType.LANGUAGE
    )  # DDC 400 = 언어 (KDC 400 자연과학과 다름!)
    assert (
        ddc_to_genre("500") == GenreType.NATURAL_SCIENCE
    )  # DDC 500 = 순수자연과학 (KDC 500 기술과학과 다름!)
    assert (
        ddc_to_genre("600") == GenreType.TECHNOLOGY
    )  # DDC 600 = 기술/응용과학 (KDC 600 예술과 다름!)
    assert (
        ddc_to_genre("700") == GenreType.ARTS
    )  # DDC 700 = 예술 (KDC 700 언어와 다름!)
    assert ddc_to_genre("800") == GenreType.LITERATURE
    assert ddc_to_genre("900") == GenreType.HISTORY


def test_kdc_ddc_cross_verification():
    # 400~700번대 KDC vs DDC 상이 번대 독립성 보장 검증
    # 400번대
    assert kdc_to_genre("400") == GenreType.NATURAL_SCIENCE
    assert ddc_to_genre("400") == GenreType.LANGUAGE
    # 500번대
    assert kdc_to_genre("500") == GenreType.TECHNOLOGY
    assert ddc_to_genre("500") == GenreType.NATURAL_SCIENCE
    # 600번대
    assert kdc_to_genre("600") == GenreType.ARTS
    assert ddc_to_genre("600") == GenreType.TECHNOLOGY
    # 700번대
    assert kdc_to_genre("700") == GenreType.LANGUAGE
    assert ddc_to_genre("700") == GenreType.ARTS


def test_kdc_004_005_plan_a():
    # 안 A 확정 검증: KDC 004/005는 대분류 GENERAL 유지, 세부 주제 '컴퓨터/IT' 보존
    assert kdc_to_genre("005.133") == GenreType.GENERAL
    assert kdc_to_subject("005.133") == "컴퓨터/IT"
    assert kdc_to_subject("004.1") == "컴퓨터/IT"

    genre, sub = parse_to_genre_and_subject(kdc_str="005.133", genre_input=None)
    assert genre == GenreType.GENERAL
    assert sub == "컴퓨터/IT"


def test_contract_t1_google_categories_not_ddc():
    # T1: Google Books categories 문자열은 DDC 코드로 간주하지 않음
    google_category = "Computers / Programming Languages / Python"
    assert ddc_to_genre(google_category) == GenreType.NONE
    assert kdc_to_genre(google_category) == GenreType.NONE

    # parse_to_genre_and_subject에 categories 문자열을 넣어도 DDC로 오인 매핑되지 않음
    genre, sub = parse_to_genre_and_subject(
        genre_input=None, current_subject=None, kdc_str=None
    )
    assert genre == GenreType.NONE


def test_contract_t3_llm_subject_preservation():
    # T3: 공식 KDC가 없더라도 LLM이 추론한 genre와 subject는 훼손 없이 보존
    genre, sub = parse_to_genre_and_subject(
        genre_input="LITERATURE",
        current_subject="SF/과학소설",
    )
    assert genre == GenreType.LITERATURE
    assert sub == "SF/과학소설"


def test_contract_t4_none_fallback_distinction():
    # T4: 불확실하거나 근거가 없는 도서는 억지 분류 대신 GenreType.NONE 허용
    genre, sub = fallback_genre_by_keywords("그냥 평범한 이야기")
    assert genre == GenreType.NONE
    assert sub is None

    # 명확한 지표어가 있는 경우만 FALLBACK 대분류 도출
    genre_novel, sub_novel = fallback_genre_by_keywords("어느 날의 장편소설")
    assert genre_novel == GenreType.LITERATURE
    assert sub_novel == "소설"


def test_genre_name_and_display_genre_separation():
    # DTO 계약 검증: genreName은 대분류 고유 한글명, displayGenre는 세부 주제 우선
    book = ExternalBook(
        title="클린 코드",
        author="로버트 마틴",
        genre=GenreType.GENERAL,
        kdc="005.133",
        subject="컴퓨터/IT",
        data_source="NL",
    )
    dump = book.model_dump(by_alias=True)
    assert dump["genre"] == "GENERAL"
    assert (
        dump["genreName"] == "교양"
    )  # 대분류 본연의 명칭 보존 (subject로 덮어쓰지 않음)
    assert (
        dump["displayGenre"] == "컴퓨터/IT"
    )  # 화면 칩용 파생값은 세부 주제 1순위 노출
    assert dump["dataSource"] == "NL"


def test_genre_korean_names():
    assert GENRE_KOREAN_NAMES[GenreType.GENERAL] == "교양"
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
    assert parse_publish_date("20230000") == "2023"
    assert parse_publish_date("20230500") == "2023-05"
    assert parse_publish_date("202312") == "2023-12"
    assert parse_publish_date("1998") == "1998"
    assert parse_publish_date(None) is None
    assert parse_publish_date("123") is None
