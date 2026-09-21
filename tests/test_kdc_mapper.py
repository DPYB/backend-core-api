from app.core.kdc_mapper import (
    GENRE_KOREAN_NAMES,
    kdc_to_genre,
    parse_page_number,
    parse_publish_date,
)
from app.models.enums import GenreType
from app.schemas.search import ExternalBook


def test_kdc_to_genre_mapping():
    # 000번대 현대 독서앱 4대 분류 매핑: 004/005는 TECHNOLOGY(컴퓨터/IT), 020은 PHILOSOPHY(독서법/글쓰기), 030/001/050은 GENERAL(교양/매거진)
    assert kdc_to_genre("005.133") == GenreType.TECHNOLOGY
    assert kdc_to_genre("004.1") == GenreType.TECHNOLOGY
    assert kdc_to_genre("029.1") == GenreType.PHILOSOPHY
    assert kdc_to_genre("030") == GenreType.GENERAL
    assert kdc_to_genre("050") == GenreType.GENERAL
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

    # 권차, 판차, 별치기호 등 부가정보가 혼합된 KDC 문자열 앵커링 정규화 검증
    # (과거 5판, [5] 등의 '5'를 첫자리로 오인하여 문학이 기술과학으로 오분류되던 치명적 버그 방지)
    assert kdc_to_genre("5판 813.6") == GenreType.LITERATURE
    assert kdc_to_genre("[5] 813.6") == GenreType.LITERATURE
    assert kdc_to_genre("813.6/005") == GenreType.LITERATURE
    assert kdc_to_genre("K813.6") == GenreType.LITERATURE
    assert kdc_to_genre("v.2 813.72") == GenreType.LITERATURE
    assert kdc_to_genre("5권 005.133") == GenreType.TECHNOLOGY

    # 도서관 청구기호 라벨 (저자기호/접두어 결합) 검증
    assert kdc_to_genre("KDC 813.6-박24ㄱ") == GenreType.LITERATURE
    assert kdc_to_genre("320.1-이38ㅅ-v.1") == GenreType.SOCIAL_SCIENCE
    assert kdc_to_genre("DDC 005.133-C12") == GenreType.TECHNOLOGY
    assert kdc_to_genre("분류기호: 813.6/005") == GenreType.LITERATURE

    # 5자리 ISBN 부가기호 (예: 03320 -> 320 사회과학, 93810 -> 810 문학, 03005 -> 005 기술과학)
    assert kdc_to_genre("03320") == GenreType.SOCIAL_SCIENCE
    assert kdc_to_genre("93810") == GenreType.LITERATURE
    assert kdc_to_genre("03005") == GenreType.TECHNOLOGY
    assert kdc_to_genre("부가기호: 03320") == GenreType.SOCIAL_SCIENCE
    assert kdc_to_genre("[03810]") == GenreType.LITERATURE


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

    # KDC 6판 800번대 문학 매핑 검증
    assert kdc_to_subject("813.7") == "SF/과학소설"
    assert kdc_to_subject("814") == "에세이/산문"
    assert kdc_to_subject("818") == "에세이/산문"
    assert kdc_to_subject("813.6") == "한국소설"
    assert kdc_to_subject("810") == "한국문학"
    assert kdc_to_subject("823") == "중국소설"
    assert kdc_to_subject("820") == "중국문학"
    assert kdc_to_subject("833") == "일본소설"
    assert kdc_to_subject("830") == "일본문학"
    assert kdc_to_subject("843") == "영미소설"  # 마션, 프로젝트 헤일메리
    assert kdc_to_subject("840") == "영미문학"
    assert kdc_to_subject("853") == "독일소설"
    assert kdc_to_subject("850") == "독일문학"
    assert kdc_to_subject("863") == "프랑스소설"
    assert kdc_to_subject("860") == "프랑스문학"
    assert kdc_to_subject("870") == "스페인문학"
    assert kdc_to_subject("880") == "이탈리아문학"
    assert kdc_to_subject("890") == "기타세계문학"
    # 기타 분류
    assert kdc_to_subject("005.133") == "컴퓨터/IT"
    assert kdc_to_subject("029") == "독서법/글쓰기"
    assert kdc_to_subject("050") == "매거진/잡지"
    assert kdc_to_subject("030") == "인문교양/상식"
    assert kdc_to_subject("189") == "심리학"
    assert kdc_to_subject("320") == "경제/경영"
    assert kdc_to_subject("03320") == "경제/경영"
    assert kdc_to_subject("93810") == "한국문학"
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
    assert sub == "컴퓨터/IT"

    genre, sub = parse_to_genre_and_subject("인문교양")
    assert genre == GenreType.GENERAL
    assert sub == "인문교양/상식"

    genre, sub = parse_to_genre_and_subject("잡지")
    assert genre == GenreType.GENERAL
    assert sub == "매거진/잡지"

    genre, sub = parse_to_genre_and_subject("독서법")
    assert genre == GenreType.PHILOSOPHY
    assert sub == "독서법/글쓰기"

    # '개발', '자기개발'이 기술과학/IT가 아닌 철학/자기계발로 매핑되는지 검증
    genre, sub = parse_to_genre_and_subject("자기개발")
    assert genre == GenreType.PHILOSOPHY
    assert sub == "자기계발"

    genre, sub = parse_to_genre_and_subject("개발")
    assert genre == GenreType.PHILOSOPHY
    assert sub == "자기계발"

    genre, sub = parse_to_genre_and_subject("소프트웨어 개발")
    assert genre == GenreType.TECHNOLOGY
    assert sub == "컴퓨터/IT"

    # 2. 영문 / 레거시 키워드 입력
    genre, sub = parse_to_genre_and_subject("literature")
    assert genre == GenreType.LITERATURE

    genre, sub = parse_to_genre_and_subject("SCIENCE_FICTION")
    assert genre == GenreType.LITERATURE
    assert sub == "SF"

    genre, sub = parse_to_genre_and_subject("self_help")
    assert genre == GenreType.PHILOSOPHY
    assert sub == "자기계발"

    # 3. KDC 분류기호 입력 (판차/권차 혼합 입력 포함)
    genre, sub = parse_to_genre_and_subject("813.7")
    assert genre == GenreType.LITERATURE
    assert sub == "SF/과학소설"

    genre, sub = parse_to_genre_and_subject("5판 813.6")
    assert genre == GenreType.LITERATURE
    assert sub == "한국소설"

    # 4. 기존 subject 보존
    genre, sub = parse_to_genre_and_subject("LITERATURE", current_subject="우주 SF")
    assert genre == GenreType.LITERATURE
    assert sub == "우주 SF"

    # 6. 도서 제목 기반 외국 SF 소설 오버라이드 (마션, 프로젝트 헤일메리 등)
    genre, sub = parse_to_genre_and_subject(
        "843",  # KDC 843 -> 영미소설
        title="마션 (화성에서 살아남기)",
    )
    assert genre == GenreType.LITERATURE
    assert sub == "SF/과학소설"

    # 제목에 SF 키워드가 없으면 영미소설 유지
    genre, sub = parse_to_genre_and_subject(
        "843",
        title="위대한 개츠비",
    )
    assert genre == GenreType.LITERATURE
    assert sub == "영미소설"

    # 7. 미술치료 / 그림의 힘 오버라이드: KDC 513.8 (기술과학/의학) -> PHILOSOPHY 승격 검증
    genre, sub = parse_to_genre_and_subject(
        "513.8",
        title="그림의 힘",
    )
    assert genre == GenreType.PHILOSOPHY
    assert sub == "미술치료/심리요법"


def test_refine_subject_by_keywords():
    from app.core.kdc_mapper import refine_subject_by_keywords

    # 영미소설 -> 마션(화성 키워드) -> SF/과학소설
    assert (
        refine_subject_by_keywords("마션", "영미소설", "화성에 고립된 우주비행사")
        == "SF/과학소설"
    )
    assert (
        refine_subject_by_keywords(
            "프로젝트 헤일메리", "영미소설", "우주를 구하기 위한 미션"
        )
        == "SF/과학소설"
    )
    assert (
        refine_subject_by_keywords("어두운 숲", "중국소설", "외계 문명의 침공")
        == "SF/과학소설"
    )
    assert (
        refine_subject_by_keywords("듄 (DUNE)", "영미소설", "SF 명작") == "SF/과학소설"
    )
    # SF 키워드가 없는 일반 소설은 원본 유지
    assert refine_subject_by_keywords("오만과 편견", "영미소설") == "영미소설"
    assert refine_subject_by_keywords("노르웨이의 숲", "일본소설") == "일본소설"
    # 1. 미술치료 / 그림의 힘 키워드 오버라이드
    assert (
        refine_subject_by_keywords(
            "그림의 힘", "건강/의학", "최고의 명화들이 주는 치유의 에너지를 담은 책"
        )
        == "미술치료/심리요법"
    )
    assert (
        refine_subject_by_keywords("누구나 쉽게 배우는 미술치료", "기타/미분류")
        == "미술치료/심리요법"
    )
    # 이미 구체적 주제가 있는 경우 유지
    assert refine_subject_by_keywords("우주론 강의", "천문학") == "천문학"


def test_display_genre_and_genre_name_prefer_subject():
    # subject가 있으면 displayGenre와 genreName 모두 subject (화면 1순위 보장)
    book_with_sub = ExternalBook(
        title="우리가 빛의 속도로 갈 수 없다면",
        author="김초엽",
        genre=GenreType.LITERATURE,
        subject="SF/과학소설",
    )
    dump1 = book_with_sub.model_dump(by_alias=True)
    assert dump1["subject"] == "SF/과학소설"
    assert dump1["genreName"] == "SF/과학소설"
    assert dump1["displayGenre"] == "SF/과학소설"

    # subject가 없으면 genreName 및 displayGenre는 KDC 한글 대분류 ("문학")
    book_without_sub = ExternalBook(
        title="일반 문학책",
        author="작가",
        genre=GenreType.LITERATURE,
        subject=None,
    )
    dump2 = book_without_sub.model_dump(by_alias=True)
    assert dump2["subject"] is None
    assert dump2["genreName"] == "문학"
    assert dump2["displayGenre"] == "문학"
