import re

from app.models.enums import GenreType

GENRE_KOREAN_NAMES = {
    GenreType.NONE: "기타/미분류",
    GenreType.GENERAL: "교양",
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


# 100~900번대 KDC 첫째 자리 대분류 매핑 상수 (O(1) 불변 룩업)
KDC_FIRST_CHAR_MAPPING: dict[str, GenreType] = {
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

# KDC 세부주제 접두사 매핑 테이블
KDC_SUBJECT_MAPPING: dict[str, str] = {
    # 800번대 문학 (한국 KDC 6판 기준 완벽 매핑: 810 한국, 820 중국, 830 일본, 840 영미, 850 독일, 860 프랑스, 870 스페인, 880 이탈리아, 890 기타)
    "813.7": "SF/과학소설",
    "814": "에세이/산문",
    "818": "에세이/산문",
    "813": "한국소설",
    "811": "한국시",
    "812": "희곡",
    "81": "한국문학",
    "823": "중국소설",
    "82": "중국문학",
    "833": "일본소설",
    "83": "일본문학",
    "843": "영미소설",
    "84": "영미문학",
    "853": "독일소설",
    "85": "독일문학",
    "863": "프랑스소설",
    "86": "프랑스문학",
    "873": "스페인소설",
    "87": "스페인문학",
    "883": "이탈리아소설",
    "88": "이탈리아문학",
    "89": "기타세계문학",
    "8": "문학",
    # 000번대 (현대 독서앱 실무 4대 카테고리)
    "004": "컴퓨터/IT",
    "005": "컴퓨터/IT",
    "02": "독서법/글쓰기",
    "05": "매거진/잡지",
    "03": "인문교양/상식",
    "00": "인문교양/상식",
    "0": "인문교양/상식",
    # 100번대 철학/심리
    "18": "심리학",
    "10": "철학/사상",
    "11": "철학/사상",
    "12": "철학/사상",
    "13": "철학/사상",
    "14": "철학/사상",
    "15": "철학/사상",
    "16": "철학/사상",
    "17": "철학/사상",
    "19": "철학/사상",
    # 300번대 사회과학/경제
    "32": "경제/경영",
    "33": "사회학/사회문제",
    # 400번대 자연과학
    "41": "수학",
    "42": "물리학",
    "43": "화학",
    "44": "천문학",
    "45": "지구과학",
    "47": "생명과학",
    # 500번대 기술과학/의학/생활
    "513.8": "미술치료/심리요법",
    "513": "건강/의학",
    "51": "건강/의학",
    "59": "요리/육아/생활",
    # 600번대 예술
    "6": "예술/문화",
    # 700번대 언어
    "7": "언어/어학",
    # 900번대 역사/지리
    "98": "여행/지리",
    "9": "역사/지리",
}

# 접두사 길이 역순(긴 것부터)으로 정렬된 키 튜플 (모듈 로딩 시 1회 계산)
_SORTED_KDC_PREFIXES: tuple[str, ...] = tuple(
    sorted(KDC_SUBJECT_MAPPING.keys(), key=len, reverse=True)
)


def extract_kdc_code(kdc_str: str | None) -> str | None:
    """
    국립중앙도서관, 서지 데이터 및 OCR 텍스트의 복합 KDC 문자열에서 실제 분류기호(숫자)를 정밀 추출하는 다계층 파이프라인.

    [우선순위 계층]
    1. 도서관 청구기호/라벨 패턴:
       - 'KDC 813.6', 'DDC 005.133', '320.1-박24ㄱ', 'K813.6-이38ㅅ', '분류: 813.6/005'
       - 저자기호(-한글/영문)나 판차/권차 등이 뒤따라도 순수 분류기호(예: '813.6', '320.1')만 분리.
    2. 5자리 ISBN 부가기호 (한국 출판유통 표준 독자·형태·내용 분류기호):
       - '03320' -> 뒤 3자리 '320' 추출, '93810' -> '810', '[03005]' -> '005'
       - 13자리 ISBN이나 가격(예: 15000원)과 혼동되지 않도록 비숫자 경계의 5자리 패턴 매칭.
    3. 표준 3자리 정수 + 선택적 소수점:
       - '813.6', '005.133', '843', '[5] 813.6', '813.6/005'
    4. 접두사/약식 1~2자리 분류기호:
       - '81', '00', '8', '0' (단, '5판', '제2권', 'v.5' 등 수식어 결합 숫자는 배제)
    """
    if not kdc_str or not kdc_str.strip():
        return None

    clean = kdc_str.strip()

    # 1. 도서관 청구기호 및 KDC/DDC 명시 접두사 라벨 패턴
    # 예: 'KDC 813.6', 'DDC 005.133', '320.1-박24ㄱ', 'K813.6-v.1', '분류기호 813.6/005'
    match_label = re.search(
        r"(?:(?:KDC|DDC|분류(?:기호)?)\s*:?\s*)?[A-Z]?(\d{3}(?:\.\d+)?)(?=[-\s/\[\(\]A-Za-z가-힣]|$)",
        clean,
        re.IGNORECASE,
    )
    if match_label:
        # 단, 앞뒤 문맥상 5자리 연속 숫자의 일부로 오매칭된 경우는 아래 2단계 부가기호로 위임
        raw_match = match_label.group(1)
        # 만약 원본 문자열에서 이 매칭 직전/직후가 숫자라면 무시하고 다음 단계 진행
        start_idx, end_idx = match_label.span(1)
        is_embedded_in_longer_number = (
            start_idx > 0 and clean[start_idx - 1].isdigit()
        ) or (end_idx < len(clean) and clean[end_idx].isdigit())
        if not is_embedded_in_longer_number:
            return raw_match

    # 2. 5자리 ISBN 부가기호 처리 (예: '03320' -> 뒤 3자리 '320' 추출, '93810' -> '810')
    # ISBN(10/13자리 연속 숫자)이나 가격(예: 15000원)과 혼동되지 않도록 비숫자 경계의 5자리 단독 패턴 매칭
    match5 = re.search(r"(?:^|[^\d])\d{2}(\d{3})(?:[^\d]|$)", clean)
    if match5:
        return match5.group(1)

    # 3. 3자리 정수 + 선택적 소수점 (예: 813.6, 005.133, 843, K813.6, [5] 813.6, 813.6/005)
    match3 = re.search(r"(?:^|[^\d])(\d{3}(?:\.\d+)?)(?:[^\d]|$)", clean)
    if match3:
        return match3.group(1)

    # 4. 접두사/약식 1~2자리 (예: '81', '00', '8', '0')
    # 판차('5판'), 권차('제2권', 'v.5') 등 한글/영문 수식어가 직전/직후에 붙은 경우 배제
    match_short = re.search(r"(?:^|[\s/\[\(])(\d{1,2}(?:\.\d+)?)(?:[\s/\]\)]|$)", clean)
    if match_short:
        return match_short.group(1)

    return None


def kdc_to_genre(kdc_str: str | None) -> GenreType:
    """
    KDC 분류기호 문자열을 판별하여 10대 대분류 ENUM으로 변환.
    - extract_kdc_code를 통해 부가정보(권차, 판차 등)를 정제한 순수 분류기호를 기준으로 판정.
    - 000번대(총류)는 도서관 고유 용어로, 현대 독서 분류에 맞춰 실제 알맹이에 따라 4대 카테고리로 라우팅:
      1) 004, 005 (컴퓨터과학, 프로그래밍, SW) -> TECHNOLOGY (기술과학/컴퓨터IT)
      2) 020 (도서관학, 서지학, 독서법, 글쓰기) -> PHILOSOPHY (철학/자기계발)
      3) 030, 001 등 (백과사전, 일반 지식, 상식) -> GENERAL (교양)
      4) 050 (잡지, 정기간행물, 매거진) -> GENERAL (교양)
    - 그 외 100~900번대는 KDC_FIRST_CHAR_MAPPING 상수를 통해 O(1) 매핑.
    """
    code = extract_kdc_code(kdc_str)
    if not code:
        return GenreType.NONE

    first_char = code[0]

    # 000번대 총류 세부 라우팅 (컴퓨터/IT, 자기계발/독서법, 교양)
    if first_char == "0":
        if code.startswith(("004", "005")):
            return GenreType.TECHNOLOGY
        if code.startswith("02"):
            return GenreType.PHILOSOPHY
        return GenreType.GENERAL

    return KDC_FIRST_CHAR_MAPPING.get(first_char, GenreType.NONE)


def kdc_to_subject(kdc_str: str | None) -> str | None:
    """
    KDC 세부분류기호로부터 구체적인 세부 주제(SF, 에세이, 소설, IT 등)를 도출.
    extract_kdc_code로 정제된 코드를 기반으로 긴 접두사부터 우선 검사하여 일관된 매핑 보장.
    """
    code = extract_kdc_code(kdc_str)
    if not code:
        return None

    for prefix in _SORTED_KDC_PREFIXES:
        if code.startswith(prefix):
            return KDC_SUBJECT_MAPPING[prefix]

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
    # 철학 / 인문 / 심리 / 심리치료
    "철학": (GenreType.PHILOSOPHY, "철학"),
    "인문": (GenreType.PHILOSOPHY, "인문학"),
    "인문학": (GenreType.PHILOSOPHY, "인문학"),
    "인문/철학": (GenreType.PHILOSOPHY, "인문/철학"),
    "심리": (GenreType.PHILOSOPHY, "심리학"),
    "심리학": (GenreType.PHILOSOPHY, "심리학"),
    "심리상담": (GenreType.PHILOSOPHY, "심리학"),
    "미술치료": (GenreType.PHILOSOPHY, "미술치료/심리요법"),
    "심리치료": (GenreType.PHILOSOPHY, "미술치료/심리요법"),
    "예술치료": (GenreType.PHILOSOPHY, "미술치료/심리요법"),
    "마음치유": (GenreType.PHILOSOPHY, "미술치료/심리요법"),
    "자기계발": (GenreType.PHILOSOPHY, "자기계발"),
    "자기개발": (GenreType.PHILOSOPHY, "자기계발"),
    "개발": (GenreType.PHILOSOPHY, "자기계발"),
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
    "재테크": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
    "투자": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
    "주식": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
    "부동산": (GenreType.SOCIAL_SCIENCE, "경제/경영"),
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
    "컴퓨터": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "컴퓨터/it": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "it": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "it/컴퓨터": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "it/프로그래밍": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "프로그래밍": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "코딩": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "소프트웨어 개발": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "웹개발": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "앱개발": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "ai": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "인공지능": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "데이터": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "컴퓨터과학": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
    "computer_it": (GenreType.TECHNOLOGY, "컴퓨터/IT"),
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
    # 교양 (총류 000 알맹이 분할: 인문교양/상식, 매거진/잡지)
    "교양": (GenreType.GENERAL, "인문교양/상식"),
    "인문교양": (GenreType.GENERAL, "인문교양/상식"),
    "인문/교양": (GenreType.GENERAL, "인문교양/상식"),
    "상식": (GenreType.GENERAL, "인문교양/상식"),
    "백과사전": (GenreType.GENERAL, "인문교양/상식"),
    "사전": (GenreType.GENERAL, "인문교양/상식"),
    "지식": (GenreType.GENERAL, "인문교양/상식"),
    "잡학": (GenreType.GENERAL, "인문교양/상식"),
    "잡지": (GenreType.GENERAL, "매거진/잡지"),
    "매거진": (GenreType.GENERAL, "매거진/잡지"),
    "간행물": (GenreType.GENERAL, "매거진/잡지"),
    "magazine": (GenreType.GENERAL, "매거진/잡지"),
    "총류": (GenreType.GENERAL, "교양"),
    "총류/교양": (GenreType.GENERAL, "교양"),
    "general": (GenreType.GENERAL, "교양"),
    # 독서법 / 글쓰기 / 자기계발 (020번대 연계)
    "독서법": (GenreType.PHILOSOPHY, "독서법/글쓰기"),
    "글쓰기": (GenreType.PHILOSOPHY, "독서법/글쓰기"),
    "작문": (GenreType.PHILOSOPHY, "독서법/글쓰기"),
    # 기타 / 미분류
    "none": (GenreType.NONE, None),
    "기타": (GenreType.NONE, None),
    "기타/미분류": (GenreType.NONE, None),
    "미분류": (GenreType.NONE, None),
}


SF_OVERRIDABLE_SUBJECTS: frozenset[str] = frozenset(
    {
        "문학",
        "소설",
        "한국문학",
        "한국소설",
        "영미소설",
        "영미문학",
        "중국소설",
        "중국문학",
        "일본소설",
        "일본문학",
        "독일소설",
        "독일문학",
        "프랑스소설",
        "프랑스문학",
        "스페인소설",
        "스페인문학",
        "이탈리아소설",
        "이탈리아문학",
        "기타세계문학",
        "장르소설",
    }
)

SF_KEYWORDS: tuple[str, ...] = (
    "sf",
    "과학소설",
    "우주",
    "외계",
    "화성",
    "달세계",
    "안드로이드",
    "사이보그",
    "타임머신",
    "스페이스 오페라",
    "사이언스 픽션",
    "science fiction",
)


THERAPY_KEYWORDS: tuple[str, ...] = (
    "미술치료",
    "그림의 힘",
    "심리치료",
    "마음치유",
    "예술치료",
)


def refine_subject_by_keywords(
    title: str | None,
    subject: str | None,
    description: str | None = None,
) -> str | None:
    """
    KDC 분류 체계의 한계(외국 문학/소설의 SF/장르 미분류, 미술치료의 기술과학 오분류)를 보완하기 위한 스마트 오버라이드.
    - 1) 문학/소설군 도서의 제목/소개글에 SF 키워드가 포함되어 있으면 'SF/과학소설'로 자동 보정.
    - 2) 도서 제목/소개글에 '미술치료', '그림의 힘' 등 심리/치유 키워드가 있으면 '미술치료/심리요법'으로 보정.
    """
    target_subject = (subject or "").strip()
    text_to_check = f"{title or ''} {description or ''}".lower()
    if not text_to_check.strip():
        return subject

    # 1. 미술치료 / 심리치유 키워드 오버라이드 (기술과학/건강/의학/미분류 등으로 빠지는 것 방지)
    if not target_subject or target_subject in (
        "건강/의학",
        "기술과학",
        "인문교양/상식",
        "기타/미분류",
        "문학",
    ):
        for kw in THERAPY_KEYWORDS:
            if kw in text_to_check:
                return "미술치료/심리요법"

    # 2. SF 키워드 오버라이드
    can_override_sf = not target_subject or target_subject in SF_OVERRIDABLE_SUBJECTS
    if can_override_sf:
        for kw in SF_KEYWORDS:
            if kw in text_to_check:
                return "SF/과학소설"

    return subject


def parse_to_genre_and_subject(
    genre_input: str | GenreType | None,
    current_subject: str | None = None,
    kdc_str: str | None = None,
    title: str | None = None,
) -> tuple[GenreType, str | None]:
    """
    국문, 영문, 키워드, Enum 인스턴스, 또는 KDC 분류번호로부터
    (표준 GenreType 대분류, 세부 주제 subject)를 유연하게 파싱.
    도서 제목(title)이 주어지면 SF 등 키워드 기반 스마트 오버라이드 수행.
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

    # 도서 제목/설명 기반 SF/치유 키워드 스마트 오버라이드
    if title:
        final_subject = refine_subject_by_keywords(title, final_subject)
        # SF로 보정되었는데 장르가 NONE이거나 미분류면 문학(LITERATURE)으로 승격
        if final_subject == "SF/과학소설" and final_genre == GenreType.NONE:
            final_genre = GenreType.LITERATURE
        elif final_subject == "미술치료/심리요법" and final_genre in (
            GenreType.NONE,
            GenreType.TECHNOLOGY,
        ):
            final_genre = GenreType.PHILOSOPHY

    return final_genre, final_subject


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
        # 00월 00일 등 미상 데이터 처리 (예: 20230000 -> 2023)
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
