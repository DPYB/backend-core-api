from app.core.ddc_mapper import (
    DDC_GENRE_MAPPING,
    ddc_to_genre,
    extract_ddc_code,
)
from app.models.enums import GenreType


def test_ddc_to_genre_mapping():
    # DDC 제23판 공식 10대 대분류 매핑 검증
    assert ddc_to_genre("005.133") == GenreType.GENERAL  # 000 총류 / 컴퓨터과학
    assert ddc_to_genre("100") == GenreType.PHILOSOPHY  # 100 철학 / 심리학
    assert ddc_to_genre("200") == GenreType.RELIGION  # 200 종교
    assert ddc_to_genre("300") == GenreType.SOCIAL_SCIENCE  # 300 사회과학
    assert ddc_to_genre("400") == GenreType.LANGUAGE  # 400 언어 (KDC 400은 자연과학)
    assert (
        ddc_to_genre("500") == GenreType.NATURAL_SCIENCE
    )  # 500 순수자연과학 (KDC 500은 기술과학)
    assert (
        ddc_to_genre("600") == GenreType.TECHNOLOGY
    )  # 600 기술과학/응용 (KDC 600은 예술)
    assert ddc_to_genre("700") == GenreType.ARTS  # 700 예술/여가 (KDC 700은 언어)
    assert ddc_to_genre("800") == GenreType.LITERATURE  # 800 문학
    assert ddc_to_genre("900") == GenreType.HISTORY  # 900 역사/지리


def test_extract_ddc_code():
    assert extract_ddc_code("DDC 005.133") == "005.133"
    assert extract_ddc_code("Dewey 813.54") == "813.54"
    assert extract_ddc_code("DDC: 616.89") == "616.89"
    assert extract_ddc_code("823") == "823"
    assert extract_ddc_code(None) is None
    assert extract_ddc_code("") is None
    assert extract_ddc_code("ABC") is None


def test_ddc_invalid_inputs():
    assert ddc_to_genre(None) == GenreType.NONE
    assert ddc_to_genre("") == GenreType.NONE
    assert ddc_to_genre("Non-numeric") == GenreType.NONE
    assert ddc_to_genre("Computers / Programming") == GenreType.NONE


def test_ddc_genre_mapping_completeness():
    # 0부터 9까지 모든 키가 유효한 GenreType에 매핑되는지 검증
    for digit in "0123456789":
        assert digit in DDC_GENRE_MAPPING
        assert isinstance(DDC_GENRE_MAPPING[digit], GenreType)
