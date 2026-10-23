import re

from app.core.ddc_mapper import ddc_to_genre
from app.core.kdc_mapper import kdc_to_genre, kdc_to_subject
from app.models.enums import GenreType

GENRE_KOREAN_NAMES: dict[GenreType, str] = {
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

# ---------------------------------------------------------------------------
# 경량 Fallback 매퍼: 공식 분류 및 LLM 부재 시 명백한 대표 지표어만 최소 매핑
# ---------------------------------------------------------------------------
# 과거의 600줄 하드코딩 안티패턴을 제거하고, 불확실한 도서는 억지 분류 대신 NONE 허용
LIGHTWEIGHT_FALLBACK_RULES: tuple[
    tuple[tuple[str, ...], GenreType, str | None], ...
] = (
    # 문학 / 소설 / SF / 에세이
    (
        ("sf", "에스에프", "과학소설", "science fiction"),
        GenreType.LITERATURE,
        "SF/과학소설",
    ),
    (("에세이", "산문집", "수필", "essay"), GenreType.LITERATURE, "에세이"),
    (("소설", "단편선", "장편소설", "fiction", "novel"), GenreType.LITERATURE, "소설"),
    (("시집", "시선집", "희곡", "poetry"), GenreType.LITERATURE, "시·희곡"),
    # 역사
    (
        ("한국사", "조선사", "세계사", "서양사", "동양사", "근현대사", "역사기행"),
        GenreType.HISTORY,
        "역사",
    ),
    # 종교
    (
        ("성경", "불경", "기도", "신학", "목회", "복음", "사찰", "기독교", "불교"),
        GenreType.RELIGION,
        "종교",
    ),
    # 경제 / 경영
    (
        ("주식투자", "부동산투자", "재테크", "거시경제", "회계학", "마케팅전략"),
        GenreType.SOCIAL_SCIENCE,
        "경제/경영",
    ),
    # 컴퓨터 / IT
    (
        (
            "프로그래밍",
            "파이썬",
            "자바스크립트",
            "코딩",
            "소프트웨어공학",
            "머신러닝",
            "딥러닝",
        ),
        GenreType.GENERAL,
        "컴퓨터/IT",
    ),
)


def fallback_genre_by_keywords(text: str | None) -> tuple[GenreType, str | None]:
    """
    공식 분류 및 LLM이 부재할 때 도서명/소개글/입력어의 명확한 핵심 지표어로 최소한의 대분류 도출.
    불확실하거나 지표어가 없으면 억지 분류하지 않고 (GenreType.NONE, None)을 정직하게 반환합니다.
    """
    if not text or not text.strip():
        return GenreType.NONE, None

    clean_text = text.lower()
    for keywords, genre, default_sub in LIGHTWEIGHT_FALLBACK_RULES:
        if any(kw in clean_text for kw in keywords):
            return genre, default_sub

    return GenreType.NONE, None


def parse_to_genre_and_subject(
    genre_input: str | GenreType | None,
    current_subject: str | None = None,
    kdc_str: str | None = None,
    ddc_str: str | None = None,
    title: str | None = None,
    catalog: str | None = None,
) -> tuple[GenreType, str | None]:
    """
    국문 대분류명, 영문 Enum명, KDC/DDC 분류기호로부터 (대분류 GenreType, 세부 주제 subject)를 파싱합니다.
    - catalog: 'KR'(기본값, KDC 우선) 또는 'US'(DDC 우선)
    - 외부/LLM이 전달한 subject는 있는 그대로 최우선 보존.
    - KDC 004/005는 대분류 GENERAL, 세부주제 '컴퓨터/IT' 도출 (안 A 확정).
    - 분류 근거가 전혀 없는 경우 억지 추론 대신 (GenreType.NONE, current_subject) 반환.
    """
    final_genre: GenreType = GenreType.NONE
    inferred_subject: str | None = None

    if isinstance(genre_input, GenreType):
        final_genre = genre_input
    elif isinstance(genre_input, str):
        cleaned = genre_input.strip()
        upper = cleaned.upper()

        # 1. 영문 Enum 대문자 변환 시도
        try:
            final_genre = GenreType[upper]
        except KeyError:
            # 2. 한글 표준 대분류명 직접 매칭
            korean_to_genre = {v: k for k, v in GENRE_KOREAN_NAMES.items()}
            if cleaned in korean_to_genre:
                final_genre = korean_to_genre[cleaned]
            elif re.match(r"^\d", cleaned):
                # 3. KDC/DDC 숫자 코드 형태 시도 (카탈로그 또는 전달된 분류체계 우선순위 존중)
                is_us_catalog = (catalog or "").upper() == "US"
                if is_us_catalog and ddc_str:
                    final_genre = ddc_to_genre(cleaned)
                elif ddc_str and not kdc_str:
                    final_genre = ddc_to_genre(cleaned)
                else:
                    final_genre = kdc_to_genre(cleaned)
                    inferred_subject = kdc_to_subject(cleaned)
            else:
                # 4. 사용자가 직접 입력한 대표 장르 지표어 (예: 'SF', '에세이') 수용
                fb_g, fb_s = fallback_genre_by_keywords(cleaned)
                if fb_g != GenreType.NONE:
                    final_genre = fb_g
                    inferred_subject = fb_s
                else:
                    final_genre = GenreType.NONE
                    inferred_subject = cleaned

    # 분류기호 기반 보완 (카탈로그 선호도 준수: US는 DDC 우선, KR은 KDC 우선)
    if final_genre == GenreType.NONE:
        is_us_catalog = (catalog or "").upper() == "US"
        if is_us_catalog and ddc_str:
            final_genre = ddc_to_genre(ddc_str)
            if not inferred_subject and ddc_str.startswith(("004", "005")):
                inferred_subject = "컴퓨터/IT"
        elif kdc_str:
            final_genre = kdc_to_genre(kdc_str)
            if not inferred_subject:
                inferred_subject = kdc_to_subject(kdc_str)
        elif ddc_str:
            final_genre = ddc_to_genre(ddc_str)
            if not inferred_subject and ddc_str.startswith(("004", "005")):
                inferred_subject = "컴퓨터/IT"

    # 기존 subject가 명시되어 있다면 그것을 최우선 유지 (LLM 및 외부 제공 주제어 보존)
    final_subject = (
        current_subject.strip()
        if current_subject and current_subject.strip()
        else inferred_subject
    )

    # 4. 여전히 NONE이고 제목이 있는 경우 경량 Fallback 시도
    if final_genre == GenreType.NONE and title:
        fb_genre, fb_sub = fallback_genre_by_keywords(title)
        if fb_genre != GenreType.NONE:
            final_genre = fb_genre
            final_subject = final_subject or fb_sub

    return final_genre, final_subject
