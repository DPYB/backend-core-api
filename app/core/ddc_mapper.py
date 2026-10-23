import re

from app.models.enums import GenreType

# ---------------------------------------------------------------------------
# DDC (듀이십진분류법 제23판) 10대 대분류 매핑
# ---------------------------------------------------------------------------
# 000: 컴퓨터과학/정보/총류 (Computer science, knowledge & systems)
# 100: 철학/심리학 (Philosophy & psychology)
# 200: 종교 (Religion)
# 300: 사회과학 (Social sciences)
# 400: 언어 (Language)          *주의: KDC는 400이 자연과학!
# 500: 자연과학 (Pure Science)   *주의: KDC는 500이 기술과학!
# 600: 기술과학 (Technology)     *주의: KDC는 600이 예술!
# 700: 예술 (Arts & recreation) *주의: KDC는 700이 언어!
# 800: 문학 (Literature)
# 900: 역사/지리 (History & geography)
DDC_GENRE_MAPPING: dict[str, GenreType] = {
    "0": GenreType.GENERAL,
    "1": GenreType.PHILOSOPHY,
    "2": GenreType.RELIGION,
    "3": GenreType.SOCIAL_SCIENCE,
    "4": GenreType.LANGUAGE,
    "5": GenreType.NATURAL_SCIENCE,
    "6": GenreType.TECHNOLOGY,
    "7": GenreType.ARTS,
    "8": GenreType.LITERATURE,
    "9": GenreType.HISTORY,
}


def extract_ddc_code(ddc_str: str | None) -> str | None:
    """
    서지 데이터 및 도서관 청구기호 라벨에서 순수 DDC 분류기호(숫자)를 정밀 추출합니다.
    1. DDC/Dewey 명시 라벨 패턴: 'DDC 005.133', 'Dewey 813.54', 'DDC: 616.89'
    2. 표준 3자리 정수 + 선택적 소수점: '005.133', '813.54', '823'
    3. 접두사/약식 1~2자리 분류기호: '00', '8', '0'
    """
    if not ddc_str or not ddc_str.strip():
        return None

    clean = ddc_str.strip()

    # 1. DDC 또는 Dewey 명시 접두사 라벨 패턴
    match_label = re.search(
        r"(?:(?:DDC|Dewey|DDC\s*Class)\s*:?\s*)?[A-Z]?(\d{3}(?:\.\d+)?)(?=[-\s/\[\(\]A-Za-z가-힣]|$)",
        clean,
        re.IGNORECASE,
    )
    if match_label:
        raw_match = match_label.group(1)
        start_idx, end_idx = match_label.span(1)
        is_embedded_in_longer_number = (
            start_idx > 0 and clean[start_idx - 1].isdigit()
        ) or (end_idx < len(clean) and clean[end_idx].isdigit())
        if not is_embedded_in_longer_number:
            return raw_match

    # 2. 3자리 정수 + 선택적 소수점 (예: 005.133, 813.54, 823)
    match3 = re.search(r"(?:^|[^\d])(\d{3}(?:\.\d+)?)(?:[^\d]|$)", clean)
    if match3:
        return match3.group(1)

    # 3. 접두사/약식 1~2자리 (예: '00', '8', '0')
    match_short = re.search(r"(?:^|[\s/\[\(])(\d{1,2}(?:\.\d+)?)(?:[\s/\]\)]|$)", clean)
    if match_short:
        return match_short.group(1)

    return None


def ddc_to_genre(ddc_str: str | None) -> GenreType:
    """
    순수 DDC(듀이십진분류법 제23판) 분류기호를 10대 대분류 GenreType으로 변환합니다.
    - 400(언어), 500(자연과학), 600(기술과학), 700(예술)의 DDC 고유 불변식을 엄격히 준수합니다.
    - 분류기호가 없거나 유효하지 않으면 GenreType.NONE을 반환합니다.
    """
    code = extract_ddc_code(ddc_str)
    if not code:
        return GenreType.NONE

    first_char = code[0]
    return DDC_GENRE_MAPPING.get(first_char, GenreType.NONE)
