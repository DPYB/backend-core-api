# ARCHITECTURE (현재 상태)

이 문서는 지금 시점의 실제 기술 스택·구조·컨벤션만 담는다. 결정 이유는 `DECISIONS.md`, 진행 상황은 `STATE.md`를 본다.

## 1. 기술 스택
- **Language & Runtime**: Python 3.12 (CPython)
- **Web Framework**: FastAPI, Uvicorn
- **ORM & Database Tooling**: SQLAlchemy 2.0 (비동기 `asyncpg`), Alembic
- **Validation & Serialization**: Pydantic v2 (CamelCase 직렬화 베이스 `CamelModel` 및 `@computed_field`)
- **Testing**: pytest, pytest-asyncio, aiosqlite (인메모리 비동기 테스트)
- **External Communication**: httpx (국립중앙도서관 서지정보 API, AI 에이전트 벡터화 트리거)
- **Container & Deployment**: Docker (Python 3.12-slim 멀티스테이지), docker-compose, GitHub Actions

## 2. 저장소 및 패키지 구조

```
backend-core-api/
├── AGENTS.md                  # 실질적 규칙집 및 워크플로우
├── CLAUDE.md                   # Claude Code용 얇은 어댑터
├── .kiro/steering/project.md   # Kiro용 얇은 어댑터
├── .harness/                   # 하네스 상태 및 히스토리 문서 6종
├── .github/workflows/          # GitHub Actions (ci.yml, lint-pr.yml - 중앙 Reusable 호출)
├── alembic/                    # DB 마이그레이션 스크립트 (core, record, member 스키마)
├── app/
│   ├── main.py                 # FastAPI 앱 팩토리, CORS 미들웨어, 라우터 등록
│   ├── config.py               # Pydantic BaseSettings 환경설정 (DB, JWT, 외부API)
│   ├── core/
│   │   ├── exceptions.py       # 18종 표준 App Exception 및 Global Exception Handler
│   │   ├── security.py         # 자체 JWT 발급/갱신(HS256) 및 Bearer 토큰 member_id(UUID) 검증
│   │   ├── shelf_rank.py       # 62진수 LexoRank 순서 정렬 및 rebalance 알고리즘
│   │   └── kdc_mapper.py       # KDC 대분류 변환 및 한글 장르 라벨 매퍼
│   ├── db/
│   │   ├── base.py             # Base DeclarativeBase, BigIntPK (SQLite 호환)
│   │   └── session.py          # asyncpg 엔진(statement_cache_size=0) 및 get_db 의존성
│   ├── models/                 # SQLAlchemy ORM 엔티티 (Shelf, LibraryBook, Scrap, Librarian, Record, Member, Terms)
│   ├── schemas/                # Pydantic DTO 스키마 (Shelf, LibraryBook, Scrap, Librarian, Record, Auth, Member, Terms)
│   ├── services/               # 비즈니스 서비스 계층 (MemberService, SocialAuthService, TermsService 등)
│   └── routers/                # API 엔드포인트 라우터 계층 (auth, users, terms, books, shelves, scraps, librarians, records, health)
├── tests/                      # pytest 비동기 단위 및 통합 테스트 슈트 (50개)
├── Dockerfile                  # Render / Cloud Run / 로컬 공용 멀티스테이지 컨테이너
├── docker-compose.yml          # 로컬 핫리로드 개발 환경
├── pyproject.toml / requirements.txt
└── README.md
```

## 3. 데이터베이스 및 스키마 격리 정책

MSA 원칙인 'Database-per-Service'를 단일 Supabase 무료 인스턴스 안에서 구현하기 위해 **PostgreSQL 스키마(Schema) 분리**를 적용합니다:
- **`core` 스키마**: 서재 책장(`shelf`), 서재 도서(`library_book`), 도서 문장 스크랩(`scrap`), 사서 마스터(`librarian_type_info`), 사서 레벨(`librarian_level`), 회원 소유 사서(`librarian`) 소유.
- **`record` 스키마**: 독서 감상 기록(`records`), 독서록 문장 스크랩(`scraps`) 소유.
- **`member` 스키마**: 회원 프로필(`members`), 약관 마스터(`terms`), 약관 동의/철회 이력(`member_agreements`) 소유.
- **독서 기록 및 회원 데이터 영속화 단일 소유권(SSOT)**: 회원 인증/프로필, 독서 감상 기록 및 서재 도메인의 모든 RDBMS 영속화와 CRUD 비즈니스 로직을 본 레포지토리(`backend-core-api`)가 독점 소유합니다. AI 에이전트 서비스(`backend-ai-agent`)는 직접 PostgreSQL을 다루지 않고 벡터 검색 및 대화 추론에 집중하며, 필요 시 본 API를 호출합니다.
- **연결 옵션**: `search_path=core` 적용 및 트랜잭션 풀러(6543) 충돌 방지 `statement_cache_size=0`.

## 4. 핵심 도메인 불변식

1. **소셜 로그인 & 회원 자동 가입(Get-or-Create)**: Google `id_token` 또는 Kakao `access_token` 검증 후 회원 신규 가입 시 기본 책장(`Default Shelf`) 및 초기 대표 사서(`CAT`)를 자동 생성/지급합니다.
2. **LexoRank (`ShelfRank`)**: 책장 내 도서 순서는 62진수 문자열로 저장되며, 이웃 도서 간 중간값(`between`)을 계산해 순서를 부여합니다. 키 공간 소진 시 자동으로 전체 책장 도서를 균등 재분배(`rebalanced_sequence`)합니다.
3. **KDC 장르 및 화면 표시용 세부 주제(`displayGenre`)**: KDC 10대 대분류 ENUM(`genre`)을 저장하며, 소수점 세부분류기호(`kdc_to_subject`) 및 AI 에이전트/프론트엔드 입력으로부터 세부 주제(`subject`: SF, 에세이, IT 등)를 자동 추출합니다. 화면 표시용 `displayGenre`는 `subject`를 최우선 노출하고 없을 때만 대분류 `genreName`("문학" 등)으로 계층형 폴백(`@computed_field`)합니다.
4. **기본 책장(Default Shelf) 보장**: 회원당 활성 기본 책장은 반드시 1개 존재(`is_default=true`)하며 삭제할 수 없습니다. 커스텀 책장 삭제 시 내부에 있던 도서들은 모두 기본 책장의 맨 뒤로 자동 이동합니다.
5. **소프트 삭제 및 전사 캐스케이드(Cascade)**:
   - 도서(`library_book`) 또는 독서 기록(`records`) 삭제 시, 소속된 스크랩(`scrap`, `scraps`)들도 동일 트랜잭션에서 함께 소프트 삭제(`deleted_at = now()`)됩니다.
   - 회원 탈퇴(`DELETE /api/v1/users/me`) 시, 회원의 서재 책장, 도서, 스크랩, 독서기록, 사서 데이터가 단일 트랜잭션에서 일괄 소프트 삭제 처리됩니다.
6. **사서 단일 대표성**: 회원은 타입당 1마리만 보유할 수 있으며, 활성 대표 사서는 회원당 최대 1마리로 유지됩니다.
7. **독서 진도율 및 완독 상태/일시 자동 동기화**: 도서 등록, 수정(`update_book`), 진도 변경(`update_progress`) 시 `current_page == total_pages`에 도달하면 `reading_status`가 `COMPLETED`로 자동 전이되고 완독 일시(`completed_at`)가 기록됩니다. 페이지가 감소하면 `READING`으로 자동 복귀되고 `completed_at`은 `None`으로 리셋됩니다.
8. **국립중앙도서관 API 인메모리 TTL 캐싱, 교보문고 CDN 표지 폴백 및 Graceful Fallback**: 동일 ISBN 반복 조회 시 인메모리 TTL 캐시(정상 도서 24시간, 미존재 도서 1시간)를 우선 활용하며, 서지정보 표지 누락 시 10/13자리 정제 ISBN 기반 교보문고 고화질 CDN(`contents.kyobobook.co.kr`)으로 0ms 즉시 결합 폴백을 제공합니다. 외부 API 타임아웃이나 서버 장애 발생 시 전체 검색 요청을 에러로 중단시키지 않고 Graceful Fallback(`book: None`)을 보장합니다.

## 5. API 계약 및 보안 컨벤션

- **소셜 로그인 및 토큰 계약**: `POST /api/v1/auth/social/{google|kakao}`를 통해 자체 Bearer JWT Access Token 및 Refresh Token 발급.
- **인증 헤더**: `Authorization: Bearer <jwt_access_token>` (`sub` 클레임의 member_id UUID 추출 및 서명/만료 검증. X-Member-Id 우회 전면 차단).
- **에러 응답 규격**: 모든 에러 응답은 `{"code": "ERROR_CODE", "message": "설명"}` 일관된 JSON 바디를 반환합니다.
- **무과금 Keep-Alive**: `/health` 엔드포인트 호출 시 Supabase에 `SELECT 1`을 수행하여 Render(15분 인바운드 트래픽)와 Supabase(7일 무쿼리 비활성화) 슬립을 1회 호출로 동시 방지합니다. 개별 크론 대신 중앙 `DPYB/.github` 레포에서 10분 주기로 일괄 핑을 수행합니다.

## 6. Git 브랜치, 커밋 컨벤션 및 CI/CD 자동화

- **브랜치 전략**: `feat/*` 단일 접두사 사용 (`feature/*` 금지). 모든 작업은 `develop` 브랜치를 기준으로 분기/머지합니다.
- **PR & 커밋 컨벤션**: `타입[적용범위]: 국문 요약` 대괄호 `[scope]` 형식 준수 (소괄호 `()` 금지, 끝마침표 `.` 금지).
  - 허용 타입: `feat`, `fix`, `refactor`, `chore`, `test`, `docs`, `style`
  - 예시: `feat[record]: 독서 감상 기록 CRUD 엔드포인트 구현`
- **인간 개입 지점 (Human Checkpoint)**: AI 에이전트는 코드 작성, 테스트, 로컬 검증, 커밋, PR 생성까지만 수행하며, `develop` 및 `main` 머지 버튼은 절대 직접 누르지 않고 사람이 최종 확인 후 클릭합니다.
- **중앙 Reusable CI 파이프라인**:
  - `.github/workflows/ci.yml`: `DPYB/.github/.github/workflows/reusable-python-ci.yml@main` (Python 3.12 린트/포맷/타입/테스트 일괄 검사)
  - `.github/workflows/lint-pr.yml`: `DPYB/.github/.github/workflows/reusable-pr-lint.yml@main` (PR 제목, 커밋 메시지, 브랜치명 자동 검사)
