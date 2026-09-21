"""
데모 계정(DEMO_MEMBER_ID) 시드 도서 및 메타데이터 단일 진실 공급원 (SSOT).
관리자 리셋 API 및 시드 스크립트에서 공유 참조하여 멱등한 복원 기준을 제공합니다.
"""

from datetime import date
from typing import Any

from app.models.enums import BookReadingStatus, GenreType

DEMO_SEED_BOOKS: list[dict[str, Any]] = [
    # === [A. 서재 상위 독서 중 도서 5권] (READING 상태 + 스크랩 1건 완비) ===
    {
        "title": "파견자들",
        "author": "김초엽",
        "isbn": "9791191587524",
        "genre": GenreType.LITERATURE,
        "kdc": "813.7",
        "subject": "한국소설",
        "publisher": "마음산책",
        "published_date": date(2023, 10, 16),
        "total_pages": 444,
        "current_page": 52,
        "reading_status": BookReadingStatus.READING,
        "completed_offset_days": None,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791191587524.jpg",
        "is_demo_target": True,
        "scraps": [
            {
                "sentence": "지상은 저주받은 땅이 아니었다. 단지 우리가 알던 형태가 아닌 다른 생명이 번성하고 있을 뿐이었다.",
                "page_number": 38,
                "memo": "지상으로 파견된 자들이 마주한 낯선 생명체들과의 조우. 경이로움과 두려움이 공존한다.",
            }
        ],
    },
    {
        "title": "불편한 편의점",
        "author": "김호연",
        "isbn": "9791161571188",
        "genre": GenreType.LITERATURE,
        "kdc": "813.7",
        "subject": "한국소설",
        "publisher": "나무옆의자",
        "published_date": date(2021, 4, 20),
        "total_pages": 268,
        "current_page": 35,
        "reading_status": BookReadingStatus.READING,
        "completed_offset_days": None,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791161571188.jpg",
        "is_demo_target": True,
        "scraps": [
            {
                "sentence": "밥을 같이 먹는다는 건, 삶의 한 조각을 나누는 일이다. 편의점 도시락 하나에도 온기가 스며들 수 있다.",
                "page_number": 28,
                "memo": "노숙자 독고 씨가 야간 알바를 하며 전하는 투박하지만 따뜻한 위로.",
            }
        ],
    },
    {
        "title": "도둑맞은 집중력",
        "author": "요한 하리",
        "isbn": "9791167740984",
        "genre": GenreType.SOCIAL_SCIENCE,
        "kdc": "331.5412",
        "subject": "사회문제",
        "publisher": "어크로스",
        "published_date": date(2023, 4, 28),
        "total_pages": 456,
        "current_page": 48,
        "reading_status": BookReadingStatus.READING,
        "completed_offset_days": None,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791167740984.jpg",
        "is_demo_target": True,
        "scraps": [
            {
                "sentence": "우리의 집중력 저하는 개인의 의지 박약이 아니라, 주의력을 낚아채 이윤을 내도록 설계된 사회적 시스템의 결과다.",
                "page_number": 42,
                "memo": "스크린 너머 알고리즘에 잠식당한 현대인의 뇌를 깨우는 통찰.",
            }
        ],
    },
    {
        "title": "클린 코드 (Clean Code)",
        "author": "로버트 C. 마틴",
        "isbn": "9788966260959",
        "genre": GenreType.TECHNOLOGY,
        "kdc": "500",
        "subject": "소프트웨어 개발",
        "publisher": "인사이트",
        "published_date": date(2013, 12, 24),
        "total_pages": 584,
        "current_page": 80,
        "reading_status": BookReadingStatus.READING,
        "completed_offset_days": None,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9788966260959.jpg",
        "is_demo_target": True,
        "scraps": [
            {
                "sentence": "보이스카우트 규칙: 캠프장은 처음 왔을 때보다 더 깨끗하게 치워놓고 떠나라. 코드도 마찬가지다.",
                "page_number": 19,
                "memo": "기능을 추가하는 것보다 유지보수하기 쉬운 단순하고 명료한 코드가 진정한 장인정신이다.",
            }
        ],
    },
    {
        "title": "그랬다고 적었다",
        "author": "김애란",
        "isbn": "9791141618575",
        "genre": GenreType.LITERATURE,
        "kdc": "818",
        "subject": "에세이",
        "publisher": "문학동네",
        "published_date": date(2024, 7, 10),
        "total_pages": 240,
        "current_page": 42,
        "reading_status": BookReadingStatus.READING,
        "completed_offset_days": None,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791141618575.jpg",
        "is_demo_target": True,
        "scraps": [
            {
                "sentence": "슬픔은 지나가는 것이 아니라 쌓여서 마침내 다른 층위의 시선과 온기를 만들어내는 지층이다.",
                "page_number": 31,
                "memo": "일상의 사소한 문장과 침묵 속에서 길어 올린 김애란 특유의 다정한 문체.",
            }
        ],
    },
    # === [B. 과거 완독 및 중반 독서 11권] (KDC 10대 장르 전 영역 골고루 분산 + 스크랩 탑재) ===
    {
        "title": "이기적 유전자",
        "author": "리처드 도킨스",
        "isbn": "9788932473901",
        "genre": GenreType.NATURAL_SCIENCE,
        "kdc": "472.01",
        "subject": "진화생물학",
        "publisher": "을유문화사",
        "published_date": date(2018, 10, 20),
        "total_pages": 552,
        "current_page": 552,
        "reading_status": BookReadingStatus.COMPLETED,
        "completed_offset_days": 12,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9788932473901.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "우리는 유전자로 알려진 이기적인 분자들을 보존하기 위해 맹목적으로 프로그램된 생존 기계다.",
                "page_number": 65,
                "memo": "도킨스가 던지는 생명관의 근본적인 전환. 문장이 뇌리에 박힌다.",
            },
            {
                "sentence": "인간에게는 다른 동물에게 없는 독특한 특성이 있다. 바로 '문화'다. 문화적 전달의 단위인 밈(meme)을 주목해야 한다.",
                "page_number": 322,
                "memo": "유전자의 한계를 넘어 문화와 사상이 전파되는 방식.",
            },
        ],
    },
    {
        "title": "사피엔스",
        "author": "유발 하라리",
        "isbn": "9788934972464",
        "genre": GenreType.HISTORY,
        "kdc": "909",
        "subject": "인류사",
        "publisher": "김영사",
        "published_date": date(2015, 11, 24),
        "total_pages": 636,
        "current_page": 636,
        "reading_status": BookReadingStatus.COMPLETED,
        "completed_offset_days": 16,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9788934972464.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "사피엔스가 번성할 수 있었던 유일한 이유는 존재하지 않는 것을 믿을 수 있는 가상의 현실 창조 능력 때문이었다.",
                "page_number": 45,
                "memo": "종교, 국가, 화폐 모두 상상 속 질서라는 통찰.",
            }
        ],
    },
    {
        "title": "침묵의 세계",
        "author": "막스 피카르트",
        "isbn": "9788972914679",
        "genre": GenreType.RELIGION,
        "kdc": "230",
        "subject": "종교철학",
        "publisher": "까치글방",
        "published_date": date(2008, 12, 1),
        "total_pages": 288,
        "current_page": 288,
        "reading_status": BookReadingStatus.COMPLETED,
        "completed_offset_days": 14,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9788972914679.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "침묵은 단순한 말의 포기가 아니다. 그것은 침묵 자체가 독립된 하나의 신성한 긍정적 세계다.",
                "page_number": 34,
                "memo": "소음 가득한 현대 사회에서 고요와 종교적 본질을 성찰하게 함.",
            }
        ],
    },
    {
        "title": "돈의 심리학",
        "author": "모건 하우절",
        "isbn": "9791191056372",
        "genre": GenreType.SOCIAL_SCIENCE,
        "kdc": "320.4",
        "subject": "재테크/투자",
        "publisher": "인플루엔셜",
        "published_date": date(2021, 1, 13),
        "total_pages": 424,
        "current_page": 424,
        "reading_status": BookReadingStatus.COMPLETED,
        "completed_offset_days": 7,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791191056372.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "돈을 버는 것보다 중요한 것은 돈을 지키는 것이며, 돈을 지키기 위해 필요한 유일한 덕목은 겸손함과 의심이다.",
                "page_number": 112,
                "memo": "투자의 성공은 지능이 아니라 감정과 태도의 문제다.",
            }
        ],
    },
    {
        "title": "마흔에 읽는 쇼펜하우어",
        "author": "강용수",
        "isbn": "9791192300818",
        "genre": GenreType.PHILOSOPHY,
        "kdc": "165",
        "subject": "서양철학",
        "publisher": "유노북스",
        "published_date": date(2023, 9, 4),
        "total_pages": 304,
        "current_page": 304,
        "reading_status": BookReadingStatus.COMPLETED,
        "completed_offset_days": 5,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791192300818.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "인생은 고통과 무료함 사이를 오가는 시계추와 같다. 고통에서 벗어나면 지루함이 찾아온다.",
                "page_number": 88,
                "memo": "고통을 삶의 본질로 담담히 인정할 때 비로소 자유가 온다.",
            },
            {
                "sentence": "남들의 시선에서 벗어나 내면의 풍요로움을 가꾸는 자만이 진정한 평온을 누릴 수 있다.",
                "page_number": 210,
                "memo": "고독을 사랑하는 법을 가르쳐주는 문장.",
            },
        ],
    },
    {
        "title": "방구석 미술관",
        "author": "조원재",
        "isbn": "9788968331862",
        "genre": GenreType.ARTS,
        "kdc": "650.4",
        "subject": "미술사",
        "publisher": "블랙피쉬",
        "published_date": date(2018, 8, 3),
        "total_pages": 352,
        "current_page": 280,
        "reading_status": BookReadingStatus.READING,
        "completed_offset_days": None,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9788968331862.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "반 고흐에게 그림은 단순한 묘사가 아니라 영혼의 절규였으며, 타인을 향한 가장 순수한 사랑의 고백이었다.",
                "page_number": 142,
                "memo": "노란색 유화 물감 너머 고흐의 진심이 느껴진다.",
            }
        ],
    },
    {
        "title": "언어의 온도",
        "author": "이기주",
        "isbn": "9791195522125",
        "genre": GenreType.LANGUAGE,
        "kdc": "710",
        "subject": "한국어에세이",
        "publisher": "말글터",
        "published_date": date(2016, 8, 19),
        "total_pages": 272,
        "current_page": 272,
        "reading_status": BookReadingStatus.COMPLETED,
        "completed_offset_days": 9,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791195522125.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "따뜻함과 차가움, 말과 글에도 온도가 있다. 당신의 언어는 몇 도쯤 될까.",
                "page_number": 15,
                "memo": "말 한마디의 무게와 온기에 대해 되돌아보게 된다.",
            }
        ],
    },
    {
        "title": "천 개의 파랑",
        "author": "천선란",
        "isbn": "9791190090261",
        "genre": GenreType.LITERATURE,
        "kdc": "813.7",
        "subject": "SF소설",
        "publisher": "허블",
        "published_date": date(2020, 8, 19),
        "total_pages": 368,
        "current_page": 368,
        "reading_status": BookReadingStatus.COMPLETED,
        "completed_offset_days": 13,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791190090261.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "우리는 모두 천천히 달릴 권리가 있다. 부서지지 않고, 서로의 온도를 느끼며.",
                "page_number": 235,
                "memo": "휴머노이드 콜리와 투데이가 건네는 가슴 뭉클한 위로.",
            }
        ],
    },
    {
        "title": "달과 6펜스",
        "author": "서머싯 몸",
        "isbn": "9788937462566",
        "genre": GenreType.LITERATURE,
        "kdc": "843",
        "subject": "영미소설",
        "publisher": "민음사",
        "published_date": date(2000, 7, 20),
        "total_pages": 316,
        "current_page": 210,
        "reading_status": BookReadingStatus.READING,
        "completed_offset_days": None,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9788937462566.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "예술이란 인간이 신의 손길을 붙잡으려 바동거리는 처절한 비명과도 같은 것이다.",
                "page_number": 128,
                "memo": "안락한 일상을 버리고 타히티로 떠난 스트릭랜드의 광기.",
            }
        ],
    },
    {
        "title": "코스모스",
        "author": "칼 세이건",
        "isbn": "9788983711892",
        "genre": GenreType.NATURAL_SCIENCE,
        "kdc": "440",
        "subject": "천문학",
        "publisher": "사이언스북스",
        "published_date": date(2006, 12, 20),
        "total_pages": 710,
        "current_page": 530,
        "reading_status": BookReadingStatus.READING,
        "completed_offset_days": None,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9788983711892.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "우리는 별에서 나온 티끌이며, 우주가 스스로를 탐구하기 위해 진화시킨 특별한 눈이다.",
                "page_number": 180,
                "memo": "우주 앞에서 한없이 작아지면서도 경이로움이 벅차오른다.",
            }
        ],
    },
    {
        "title": "지적 대화를 위한 넓고 얕은 지식 1",
        "author": "채사장",
        "isbn": "9791190313193",
        "genre": GenreType.GENERAL,
        "kdc": "001",
        "subject": "인문교양",
        "publisher": "웨일북",
        "published_date": date(2020, 2, 5),
        "total_pages": 376,
        "current_page": 376,
        "reading_status": BookReadingStatus.COMPLETED,
        "completed_offset_days": 3,
        "cover_url": "https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/9791190313193.jpg",
        "is_demo_target": False,
        "scraps": [
            {
                "sentence": "역사는 생산수단과 자본을 둘러싼 끝없는 계급 갈등의 파노라마다.",
                "page_number": 58,
                "memo": "세계의 구조를 가장 쉽게 꿰뚫어 보게 해주는 책.",
            }
        ],
    },
]

DEMO_SEED_ISBNS: set[str] = {b["isbn"] for b in DEMO_SEED_BOOKS}
DEMO_SEED_BOOKS_BY_ISBN: dict[str, dict[str, Any]] = {
    b["isbn"]: b for b in DEMO_SEED_BOOKS
}
