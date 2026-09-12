# backend-core-api

> **Python FastAPI Migration of `backend-book` Service**  
> 본 서비스는 독서 플랫폼의 **서재(Shelf), 도서(Library Book), 스크랩(Scrap), 사서(Librarian) 캐릭터 마스터 및 회원 소유권, 국립중앙도서관 서지정보 검색**을 전담하는 시스템의 단일 진실 공급원(Single Source of Truth, SSOT)입니다.

---

## 1. 기술 스택 & 아키텍처

- **Language & Framework**: Python 3.12, FastAPI, Pydantic v2
- **ORM & Database**: SQLAlchemy 2.0 (비동기 `asyncpg`), Supabase PostgreSQL (Free Tier), Alembic
- **MSA 스키마 격리**: 단일 Supabase 인스턴스 내 `core` 스키마(`search_path=core`) 독립 소유
- **Supabase Connection Pooler 호환**: 트랜잭션 풀러(포트 6543) 연동 시 `statement_cache_size=0` 적용
- **핵심 도메인 알고리즘**:
  - **LexoRank (`ShelfRank`)**: 62진수 사전식 순서 문자열 정렬 및 자동 재분배(rebalance)
  - **KDC 10대 대분류 & 한글 매핑**: `@computed_field`를 통한 `genreName` 자동 생성
  - **국립중앙도서관 API 연동**: `httpx` 비동기 클라이언트 & 서재 등록 도서 캐시 우회
  - **도메인 무결성**: Soft Delete, 도서 삭제 시 스크랩 캐스케이드 Soft Delete, 기본 책장 삭제 방지 및 도서 자동 이관, 회원별 단일 대표 사서 유지

---

## 2. API 엔드포인트 요약 (26개 엔드포인트)

| 도메인 | 메서드 | 경로 | 설명 |
| :--- | :--- | :--- | :--- |
| **시스템** | `GET` | `/health` | 서비스 헬스체크 (Public) |
| **도서 검색** | `GET` | `/api/v1/books/search?isbn={isbn}` | 국립중앙도서관 API 및 서재 기등록 도서 검색 |
| **책장 관리** | `POST` | `/api/v1/library/shelves` | 새 책장 생성 |
| | `GET` | `/api/v1/library/shelves` | 책장 목록 조회 (기본 책장 자동 생성 및 도서수 포함) |
| | `PATCH` | `/api/v1/library/shelves/{shelfId}` | 책장 이름 수정 |
| | `DELETE`| `/api/v1/library/shelves/{shelfId}` | 책장 삭제 (소속 도서는 기본 책장으로 자동 이동) |
| | `GET` | `/api/v1/library/shelves/{shelfId}/books` | 특정 책장의 도서 페이징 조회 |
| **도서 관리** | `POST` | `/api/v1/library/books` | 서재 도서 등록 (기본 책장 배치, LexoRank 순서 부여) |
| | `GET` | `/api/v1/library/books` | 서재 도서 목록 조회 (다중 필터 및 정렬 지원) |
| | `GET` | `/api/v1/library/books/{bookId}` | 도서 상세 조회 |
| | `PATCH` | `/api/v1/library/books/{bookId}` | 도서 메타데이터 전체 수정 (ADR-0006) |
| | `DELETE`| `/api/v1/library/books/{bookId}` | 도서 삭제 (소속 스크랩 캐스케이드 Soft Delete) |
| | `PATCH` | `/api/v1/library/books/{bookId}/order` | 책장 내 도서 순서 재정렬 (ADR-0004) |
| | `PATCH` | `/api/v1/library/books/{bookId}/shelf` | 다른 책장으로 이동 (ADR-0008) |
| | `PATCH` | `/api/v1/library/books/{bookId}/progress` | 독서 진도(현재 페이지) 업데이트 |
| **스크랩 관리**| `POST` | `/api/v1/library/books/{bookId}/scraps` | 문장 스크랩 등록 |
| | `GET` | `/api/v1/library/books/{bookId}/scraps` | 도서별 스크랩 페이징 목록 조회 |
| | `GET` | `/api/v1/library/scraps?bookId={id}` | 도서별 스크랩 쿼리 조회 (AI 에이전트 연동용) |
| | `GET` | `/api/v1/library/scraps/{scrapId}` | 스크랩 단건 상세 조회 |
| | `PATCH` | `/api/v1/library/scraps/{scrapId}` | 스크랩 전체 수정 |
| | `DELETE`| `/api/v1/library/scraps/{scrapId}` | 스크랩 삭제 (Soft Delete) |
| **독서 기록 관리**| `POST` | `/api/v1/records` | 독서 감상평 및 문장 스크랩 저장 (AI 벡터화 연동) |
| | `GET` | `/api/v1/records` | 사용자 독서 기록 페이징 목록 조회 |
| | `GET` | `/api/v1/records/{recordId}` | 독서 기록 단건 상세 조회 |
| | `DELETE`| `/api/v1/records/{recordId}` | 독서 기록 및 소속 스크랩 Soft Delete Cascade |
| **사서 관리** | `GET` | `/api/v1/librarian-types` | 사서 4종 마스터 카탈로그 조회 |
| | `POST` | `/api/v1/librarians` | 사서 획득/입양 (동일 타입 중복 방지) |
| | `GET` | `/api/v1/librarians` | 내가 보유한 사서 목록 조회 |
| | `GET` | `/api/v1/librarians/representative` | 회원의 대표 사서 조회 |
| | `PATCH` | `/api/v1/librarians/{id}/representative` | 대표 사서 지정 (단일 대표 보장) |
| | `PATCH` | `/api/v1/librarians/{id}` | 사서 개명 |
| | `DELETE`| `/api/v1/librarians/{id}` | 사서 방출 (Soft Delete) |

---

## 3. 로컬 개발 및 실행 가이드

### 3.1 가상환경 생성 및 의존성 설치
```bash
# Python 3.12 가상환경 생성
uv venv --python 3.12 .venv
source .venv/bin/activate

# 의존성 설치
uv pip install -r requirements.txt
```

### 3.2 환경변수 설정
```bash
cp .env.example .env
# .env 파일을 열고 Supabase DATABASE_URL, AUTH_APP_CLIENT_ID, NL_API_CERT_KEY 등을 설정합니다.
```

### 3.3 데이터베이스 마이그레이션 (Alembic)
```bash
# core 스키마 및 테이블 생성 + 초기 시드 데이터 적용
alembic upgrade head
```

### 3.4 로컬 서버 구동
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Swagger API 문서: `http://localhost:8000/docs`
- 헬스체크: `http://localhost:8000/health`

### 3.5 테스트 실행 (pytest)
```bash
# 전체 테스트 실행 (단위 및 통합 테스트 41개)
pytest -v
```

---

## 4. Docker 및 배포 전략

### 4.1 로컬 Docker Compose 실행
```bash
docker compose up --build
```

### 4.2 프로덕션 배포 (Render / Google Cloud Run 호환)
동일한 `Dockerfile`이 Render의 `$PORT` 동적 바인딩 및 Google Cloud Run의 기본 포트 바인딩을 자동으로 지원합니다.
```bash
# Google Cloud Run 배포 예시
gcloud run deploy virtual-shelf-book-api \
  --source . \
  --region asia-northeast3 \
  --platform managed \
  --allow-unauthenticated
```