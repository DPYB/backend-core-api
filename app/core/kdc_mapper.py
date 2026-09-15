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

    clean = kdc_str.strip()
    match = re.search(r"\d", clean)
    if not match:
        return GenreType.NONE

    first_char = match.group()
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


def kdc_to_subject(kdc_str: str | None) -> str | None:
    """
    KDC 세부분류기호로부터 구체적인 세부 주제(SF, 에세이, 소설, IT 등)를 도출.
    사용자 화면(UI)에 대분류('문학') 대신 직관적인 세부 주제를 우선 노출하기 위해 활용.
    예: '813.7' -> 'SF/과학소설', '818' -> '에세이/산문', '005.133' -> 'IT/프로그래밍'
    """
    if not kdc_str or not kdc_str.strip():
        return None

    clean = kdc_str.strip()

    # 1. 800번대 문학 세부분류
    if clean.startswith("813.7"):
        return "SF/과학소설"
    if clean.startswith(("814", "818")):
        return "에세이/산문"
    if clean.startswith("813"):
        return "한국소설"
    if clean.startswith("811"):
        return "한국시"
    if clean.startswith("812"):
        return "희곡"
    if clean.startswith("823"):
        return "영미소설"
    if clean.startswith("82"):
        return "영미문학"
    if clean.startswith("83"):
        return "독일문학"
    if clean.startswith("84"):
        return "프랑스문학"
    if clean.startswith("85"):
        return "이탈리아문학"
    if clean.startswith("86"):
        return "스페인문학"
    if clean.startswith("893"):
        return "일본문학"
    if clean.startswith("892"):
        return "중국문학"
    if clean.startswith("89"):
        return "기타세계문학"
    if clean.startswith("8"):
        return "문학"

    # 2. 000번대 총류/컴퓨터
    if clean.startswith(("004", "005")):
        return "IT/프로그래밍"

    # 3. 100번대 철학/심리
    if clean.startswith("18"):
        return "심리학"
    if clean.startswith(("10", "11", "12", "13", "14", "15", "16", "17", "19")):
        return "철학/사상"

    # 4. 300번대 사회과학/경제
    if clean.startswith("32"):
        return "경제/경영"
    if clean.startswith("33"):
        return "사회학/사회문제"

    # 5. 400번대 자연과학
    if clean.startswith("41"):
        return "수학"
    if clean.startswith("42"):
        return "물리학"
    if clean.startswith("43"):
        return "화학"
    if clean.startswith("44"):
        return "천문학"
    if clean.startswith("45"):
        return "지구과학"
    if clean.startswith("47"):
        return "생명과학"

    # 6. 500번대 기술과학
    if clean.startswith("51"):
        return "건강/의학"
    if clean.startswith("59"):
        return "요리/육아/생활"

    # 7. 600번대 예술
    if clean.startswith("6"):
        return "예술/문화"

    # 8. 700번대 언어
    if clean.startswith("7"):
        return "언어/어학"

    # 9. 900번대 역사/지리
    if clean.startswith("98"):
        return "여행/지리"
    if clean.startswith("9"):
        return "역사/지리"

    return None


# 국문/영문/키워드 -> (대분류 GenreType, 세부 주제 subject) 매핑 테이블
GENRE_KEYWORD_MAPPING: dict[str, tuple[GenreType, str | None]] = {
    # SF / 과학소설
    "sf": (GenreType.LITERATURE, "SF"),
    "에스에프": (GenreType.LITERATURE, "SF"),
    "과학소설": (GenreType.LITERATURE, "SF"),
    "sf소설": (GenreType.LITERATURE, "SF"),
    "science fiction": (GenreType.LITERATURE, "SF"),
    "science_fiction": (GenreType.LITERATURE, "SF"),
    # 에세이 / 산문
    "에세이": (GenreType.LITERATURE, "에세이"),
    "산문": (GenreType.LITERATURE, "에세이"),
    "수필": (GenreType.LITERATURE, "에세이"),
    "essay": (GenreType.LITERATURE, "에세이"),
    # 소설 / 문학
    "소설": (GenreType.LITERATURE, "소설"),
    "한국소설": (GenreType.LITERATURE, "한국소설"),
    "장르소설": (GenreType.LITERATURE, "장르소설"),
    "문학": (GenreType.LITERATURE, None),
    "문학/소설": (GenreType.LITERATURE, "소설"),
    "fiction": (GenreType.LITERATURE, "소설"),
    "novel": (GenreType.LITERATURE, "소설"),
    "literature": (GenreType.LITERATURE, None),
    "literary_fiction": (GenreType.LITERATURE, "소설"),
    # 시 / 희곡
    "시": (GenreType.LITERATURE, "시·희곡"),
    "시집": (GenreType.LITERATURE, "시·희곡"),
    "희곡": (GenreType.LITERATURE, "시·희곡"),
    "시/희곡": (GenreType.LITERATURE, "시·희곡"),
    "시·희곡": (GenreType.LITERATURE, "시·희곡"),
    "poetry": (GenreType.LITERATURE, "시·희곡"),
    "poetry_drama": (GenreType.LITERATURE, "시·희곡"),
    # 추리 / 미스터리 / 스릴러
    "추리": (GenreType.LITERATURE, "미스터리·스릴러"),
    "미스터리": (GenreType.LITERATURE, "미스터리·스릴러"),
    "스릴러": (GenreType.LITERATURE, "미스터리·스릴러"),
    "추리소설": (GenreType.LITERATURE, "미스터리·스릴러"),
    "미스터리/스릴러": (GenreType.LITERATURE, "미스터리·스릴러"),
    "미스터리·스릴러": (GenreType.LITERATURE, "미스터리·스릴러"),
    "mystery": (GenreType.LITERATURE, "미스터리·스릴러"),
    "thriller": (GenreType.LITERATURE, "미스터리·스릴러"),
    "mystery_thriller": (GenreType.LITERATURE, "미스터리·스릴러"),
    # 판타지 / 로맨스
    "판타지": (GenreType.LITERATURE, "판타지"),
    "fantasy": (GenreType.LITERATURE, "판타지"),
    "로맨스": (GenreType.LITERATURE, "로맨스"),
    "romance": (GenreType.LITERATURE, "로맨스"),
    # 철학 / 인문 / 심리
    "철학": (GenreType.PHILOSOPHY, "철학"),
    "인문": (GenreType.PHILOSOPHY, "인문학"),
    "인문학": (GenreType.PHILOSOPHY, "인문학"),
    "인문/철학": (GenreType.PHILOSOPHY, "인문/철학"),
    "심리": (GenreType.PHILOSOPHY, "심리학"),
    "심리학": (GenreType.PHILOSOPHY, "심리학"),
    "자기계발": (GenreType.PHILOSOPHY, "자기계발"),
    "self_help": (GenreType.PHILOSOPHY, "자기계발"),
    "humanities": (GenreType.PHILOSOPHY, "인문학"),
    "philosophy": (GenreType.PHILOSOPHY, "철학"),
    "psychology": (GenreType.PHILOSOPHY, "심리학"),
    # 종교
    "종교": (GenreType.RELIGION, "종교"),
    "religion": (GenreType.RELIGION, "종교"),
    # 사회과학 / 경제 / 경영
    "사회과학": (GenreType.SOCIAL_SCIENCE, "사회과학"),
    "사회": (GenreType.SOCIAL_SCIENCE, "사회과학"),
    "경제": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
    "경영": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
    "경제/경영": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
    "비즈니스": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
    "business_economics": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
    "social_science": (GenreType.SOCIAL_SCIENCE, "사회과학"),
    "economics": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
    # 자연과학
    "자연과학": (GenreType.NATURAL_SCIENCE, "자연과학"),
    "과학": (GenreType.NATURAL_SCIENCE, "자연과학"),
    "natural_science": (GenreType.NATURAL_SCIENCE, "자연과학"),
    "science": (GenreType.NATURAL_SCIENCE, "자연과학"),
    # 기술과학 / IT
    "기술과학": (GenreType.TECHNOLOGY, "기술과학"),
    "기술": (GenreType.TECHNOLOGY, "기술/공학"),
    "기술/공학": (GenreType.TECHNOLOGY, "기술/공학"),
    "공학": (GenreType.TECHNOLOGY, "기술/공학"),
    "컴퓨터": (GenreType.TECHNOLOGY, "IT/컴퓨터"),
    "it": (GenreType.TECHNOLOGY, "IT/컴퓨터"),
    "it/컴퓨터": (GenreType.TECHNOLOGY, "IT/컴퓨터"),
    "프로그래밍": (GenreType.TECHNOLOGY, "IT/프로그래밍"),
    "computer_it": (GenreType.TECHNOLOGY, "IT/컴퓨터"),
    "technology": (GenreType.TECHNOLOGY, "기술과학"),
    # 예술
    "예술": (GenreType.ARTS, "예술"),
    "미술": (GenreType.ARTS, "예술"),
    "음악": (GenreType.ARTS, "예술"),
    "arts": (GenreType.ARTS, "예술"),
    "art": (GenreType.ARTS, "예술"),
    # 언어
    "언어": (GenreType.LANGUAGE, "언어"),
    "어학": (GenreType.LANGUAGE, "언어"),
    "language": (GenreType.LANGUAGE, "언어"),
    # 역사
    "역사": (GenreType.HISTORY, "역사"),
    "history": (GenreType.HISTORY, "역사"),
    # 총류
    "총류": (GenreType.GENERAL, "총류"),
    "총류/교양": (GenreType.GENERAL, "총류"),
    "general": (GenreType.GENERAL, "총류"),
    # 기타 / 미분류
    "none": (GenreType.NONE, None),
    "기타": (GenreType.NONE, None),
    "기타/미분류": (GenreType.NONE, None),
    "미분류": (GenreType.NONE, None),
}


def parse_to_genre_and_subject(
    genre_input: object,
    current_subject: str | None = None,
    kdc_str: str | None = None,
) -> tuple[GenreType, str | None]:
    """
    국문, 영문, 키워드, Enum 인스턴스, 또는 KDC 분류번호로부터
    (표준 GenreType 대분류, 세부 주제 subject)를 유연하게 파싱.
    """
    final_genre: GenreType = GenreType.NONE
    inferred_subject: str | None = None

    if isinstance(genre_input, GenreType):
        final_genre = genre_input
    elif isinstance(genre_input, str):
        cleaned = genre_input.strip()
        normalized_key = cleaned.lower()

        # 1. 키워드 매핑 테이블 조회
        if normalized_key in GENRE_KEYWORD_MAPPING:
            mapped_genre, mapped_sub = GENRE_KEYWORD_MAPPING[normalized_key]
            final_genre = mapped_genre
            inferred_subject = mapped_sub
        else:
            # 2. 영문 Enum 대문자 변환 시도
            try:
                final_genre = GenreType[cleaned.upper()]
            except KeyError:
                # 3. KDC/DDC 숫자 코드 형태 시도
                if re.match(r"^\d", cleaned):
                    final_genre = kdc_to_genre(cleaned)
                    inferred_subject = kdc_to_subject(cleaned)
                else:
                    # 알 수 없는 임의의 텍스트인 경우: 대분류는 NONE, 사용자의 입력을 주제로 보존
                    final_genre = GenreType.NONE
                    inferred_subject = cleaned

    # KDC 문자열이 있고 아직 세부 주제가 추론되지 않았다면 KDC 세부주제 도출
    if not inferred_subject and kdc_str:
        inferred_subject = kdc_to_subject(kdc_str)

    # 기존 subject가 명시되어 있다면 그것을 최우선 유지
    final_subject = (
        current_subject.strip()
        if current_subject and current_subject.strip()
        else inferred_subject
    )

    return final_genre, final_subject


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
