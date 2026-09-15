from enum import Enum
from typing import Any


class GenreType(str, Enum):
    NONE = "NONE"
    GENERAL = "GENERAL"  # 000 총류
    PHILOSOPHY = "PHILOSOPHY"  # 100 철학
    RELIGION = "RELIGION"  # 200 종교
    SOCIAL_SCIENCE = "SOCIAL_SCIENCE"  # 300 사회과학
    NATURAL_SCIENCE = "NATURAL_SCIENCE"  # 400 자연과학
    TECHNOLOGY = "TECHNOLOGY"  # 500 기술과학
    ARTS = "ARTS"  # 600 예술
    LANGUAGE = "LANGUAGE"  # 700 언어
    LITERATURE = "LITERATURE"  # 800 문학
    HISTORY = "HISTORY"  # 900 역사


class BookReadingStatus(str, Enum):
    PLANNED = "PLANNED"
    READING = "READING"
    COMPLETED = "COMPLETED"


class LibrarianType(str, Enum):
    CAT = "CAT"  # 러시안 블루 사서 (기본 표시명: 블루)
    SHOEBILL = "SHOEBILL"  # 넙적부리황새 사서 (기본 표시명: 슈빌)
    SEA_SLUG = "SEA_SLUG"  # 갯민숭달팽이 사서 (기본 표시명: 누디)
    GECKO = "GECKO"  # 게코 도마뱀 사서 (기본 표시명: 게코)

    # 레거시 호환 별칭
    RUSSIAN_BLUE = "CAT"


# 사서 4종 페르소나 및 기본 표시명 메타데이터 카탈로그
LIBRARIAN_METADATA: dict[LibrarianType, dict[str, Any]] = {
    LibrarianType.CAT: {
        "species": "러시안 블루",
        "default_name": "블루",
        "mbti": "INTJ",
        "genres": ["총류", "철학", "종교"],
        "description": "본질을 파고드는 사색가",
        "ending_style": "~냥",
    },
    LibrarianType.SHOEBILL: {
        "species": "넙적부리황새",
        "default_name": "슈빌",
        "mbti": "ISTP",
        "genres": ["자연과학", "기술과학"],
        "description": "원리와 작동 방식을 탐구하는 실용가",
        "ending_style": "~두둥",
    },
    LibrarianType.SEA_SLUG: {
        "species": "갯민숭달팽이",
        "default_name": "누디",
        "mbti": "INFP",
        "genres": ["예술", "문학"],
        "description": "감수성이 풍부한 감성가",
        "ending_style": "~누누",
    },
    LibrarianType.GECKO: {
        "species": "게코 도마뱀",
        "default_name": "게코",
        "mbti": "ENFJ",
        "genres": ["사회과학", "언어", "역사"],
        "description": "사람과 사회를 잇는 공감형 탐구자",
        "ending_style": "~크크",
    },
}

# 기본 표시명 딕셔너리
DEFAULT_LIBRARIAN_NAMES: dict[LibrarianType, str] = {
    lib_type: str(meta["default_name"]) for lib_type, meta in LIBRARIAN_METADATA.items()
}
