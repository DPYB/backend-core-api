from enum import Enum


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
    CAT = "CAT"  # 고양이 사서
    SHOEBILL = "SHOEBILL"  # 슈빌 새 사서
    SEA_SLUG = "SEA_SLUG"  # 바다 달팽이 사서
    GECKO = "GECKO"  # 게코 도마뱀 사서

    # 레거시 호환 별칭
    RUSSIAN_BLUE = "CAT"
