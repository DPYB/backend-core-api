"""
ISBN Validation, Conversion, and Normalization Utilities.

규칙:
1. ISBN-10: Modulo 11 검증 (마지막 자리는 숫자 또는 'X'/'x').
2. ISBN-10 -> ISBN-13 변환:
   - 반드시 유효한 ISBN-10인지 먼저 검증.
   - 앞 9자리에 '978' 접두사를 붙여 12자리 구성.
   - EAN-13 가중치(1, 3 교대)로 13번째 체크디지트를 새롭게 산출.
3. ISBN-13: EAN-13 가중치 체크디지트 검증.
4. 정규화(normalize_isbn):
   - None이거나 공백/빈 문자열인 경우 None 반환.
   - 하이픈과 공백 제거, 소문자 x는 대문자 X로 정규화.
   - 유효한 ISBN-10은 변환된 13자리 표준 ISBN 반환.
   - 유효한 ISBN-13은 13자리 표준 ISBN 반환.
   - 체크디지트 오류, 부적합한 길이, 숫자가 아닌 문자가 포함된 경우 ValueError 발생.
"""

import re


def validate_isbn10(isbn10: str | None) -> bool:
    """Validate an ISBN-10 string using the Modulo 11 check digit algorithm."""
    if not isbn10 or not isinstance(isbn10, str):
        return False
    clean = re.sub(r"[-\s]", "", isbn10).upper()
    if len(clean) != 10:
        return False
    if not clean[:9].isdigit():
        return False
    last_char = clean[9]
    if not (last_char.isdigit() or last_char == "X"):
        return False
    s = sum(int(clean[i]) * (10 - i) for i in range(9))
    check = 10 if last_char == "X" else int(last_char)
    s += check
    return (s % 11) == 0


def calculate_isbn13_check_digit(raw12: str) -> str:
    """Calculate the 13th check digit for a 12-digit string according to EAN-13 rules."""
    if not raw12 or len(raw12) != 12 or not raw12.isdigit():
        raise ValueError(f"raw12 must be a 12-digit numeric string, got '{raw12}'")
    s = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(raw12))
    check = (10 - (s % 10)) % 10
    return str(check)


def validate_isbn13(isbn13: str | None) -> bool:
    """Validate an ISBN-13 string using the EAN-13 check digit algorithm."""
    if not isbn13 or not isinstance(isbn13, str):
        return False
    clean = re.sub(r"[-\s]", "", isbn13)
    if len(clean) != 13 or not clean.isdigit():
        return False
    expected_check = calculate_isbn13_check_digit(clean[:12])
    return clean[12] == expected_check


def convert_isbn10_to_isbn13(isbn10: str | None) -> str:
    """Convert a valid ISBN-10 to an ISBN-13 by recalculating the 13th check digit.

    Raises ValueError if isbn10 is invalid.
    """
    clean = re.sub(r"[-\s]", "", (isbn10 or "")).upper()
    if not validate_isbn10(clean):
        raise ValueError("유효하지 않은 10자리 ISBN입니다.")
    raw12 = "978" + clean[:9]
    check_digit = calculate_isbn13_check_digit(raw12)
    return raw12 + check_digit


def normalize_isbn(isbn: str | None) -> str | None:
    """Normalize and validate an ISBN string into a standard 13-digit numeric ISBN string.

    Returns:
        13-digit standard ISBN string if valid, or None if input is None or blank.

    Raises:
        ValueError: If the ISBN has invalid format, length, or check digit.
    """
    if isbn is None:
        return None

    cleaned = re.sub(r"[-\s]", "", str(isbn).strip()).upper()
    if not cleaned:
        return None

    if len(cleaned) == 10:
        if not validate_isbn10(cleaned):
            raise ValueError("유효하지 않은 10자리 ISBN 체크디지트입니다.")
        return convert_isbn10_to_isbn13(cleaned)
    elif len(cleaned) == 13:
        if not validate_isbn13(cleaned):
            raise ValueError("유효하지 않은 13자리 ISBN 체크디지트입니다.")
        return cleaned
    else:
        raise ValueError(
            f"ISBN은 10자리 또는 13자리여야 합니다. (입력 길이: {len(cleaned)}자리)"
        )
