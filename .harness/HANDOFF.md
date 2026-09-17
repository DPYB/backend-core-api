# HANDOFF (세션별 서술 로그, append-only)

## 2026-09-11: FastAPI 마이그레이션 및 도메인 API 전수 구축
- 기존 Java/Spring Boot `backend-book` 서비스를 Python 3.12, FastAPI, SQLAlchemy 2.0 (asyncpg), Alembic, Pydantic V2 스택으로 마이그레이션 완료.
- Supabase PostgreSQL `core` 스키마 격리 DDL 및 ORM 모델 6종(`shelf`, `library_book`, `scrap`, `librarian_type_info`, `librarian_level`, `librarian`) 구축.
- 62진수 LexoRank(`ShelfRank`) 정렬 알고리즘, KDC 10대 대분류 매퍼(`@computed_field genreName`), 국립중앙도서관 비동기 도서 검색 클라이언트(`httpx`) 구현.
- 18종 표준 에러 처리 및 26개 API 엔드포인트 전수 구현 완료.
- 총 41개 단위/통합 테스트 작성 및 100% 통과 검증.

## 2026-09-11: 무과금(Zero-Cost) 배포 정책 최적화
- `/health` 엔드포인트에 Supabase `SELECT 1` 쿼리 실행 로직을 연동하여, 1회의 헬스체크로 Render(15분 인바운드 트래픽)와 Supabase(7일 무쿼리 비활성화) 슬립을 동시 방지하도록 개선.
- `CORS_ORIGINS` 환경변수를 분리하여 Cloudflare 프론트엔드 도메인을 안전하게 화이트리스트에 등록할 수 있도록 설정.
- `.github/workflows/keep-alive.yml` GitHub Actions 크론(14분 간격)을 구축하여 $0 무과금 상시 가동 환경 완성.
- 사서 대표 타입을 명세서 최종본에 맞춰 `CAT`으로 확정 반영 (레거시 `RUSSIAN_BLUE` 별칭 호환).

## 2026-09-12: 독서 감상 기록(Record) CRUD 통합 & 하네스 표준 구축
- `backend-record` 서비스의 독서 감상 기록(Record) 및 스크랩(Scrap) 원본 영속화 CRUD를 `backend-core-api`로 일원화 (단일 진실 공급원 SSOT 확립).
- `record.records`, `record.scraps` 테이블 DDL 및 Alembic 리비전(`002_add_record_schema.py`) 작성.
- 독서 기록 소프트 삭제 시 연결된 스크랩 일괄 소프트 삭제(Soft Delete Cascade) 및 AI 벡터화(`trigger_ai_vectorization`) 비동기 트리거 구현.
- `X-Member-Id` 헤더 검증 및 422 Unprocessable Entity 에러 처리 반영, 총 44개 테스트 100% 통과.
- DPYB 조직 공통 [바이브 코딩 하네스 표준] 구축 완료 (`AGENTS.md`, `CLAUDE.md`, `.kiro/`, `.harness/` 6개 문서).

## 2026-09-13: 중앙 Reusable CI 연동 및 DPYB 최신 개발 표준 하네스 전면 동기화
- **워크플로우 정비**:
  - 개별 킵얼라이브(`.github/workflows/keep-alive.yml`)를 삭제하고, `DPYB/.github` 중앙 레포의 10분 주기 일괄 헬스체크 핑 연동으로 일원화.
  - `/health` 엔드포인트의 Supabase `SELECT 1` 실행 및 에러 처리 보장 로직 유지 확인.
  - `.github/workflows/ci.yml` 및 `.github/workflows/lint-pr.yml`을 구성하여 중앙 Reusable 워크플로우(`reusable-python-ci.yml`, `reusable-pr-lint.yml`) 연동 완료.
- **코드 품질 및 의존성 정비**:
  - `pyproject.toml`에 `greenlet>=3.0.0`, `ruff>=0.3.0`, `mypy>=1.9.0` 설정 추가 및 코드베이스 전체 `ruff check`, `ruff format` 일괄 정리. (44개 pytest 100% Pass)
- **하네스 문서 최신 표준 명문화**:
  - `AGENTS.md`, `.harness/ARCHITECTURE.md`, `docs/HARNESS_SETUP_GUIDE.md`:
    1. 브랜치는 `feat/*` 단일 접두사 사용 (`feature/*` 금지, `develop` 기본 분기/머지).
    2. PR 및 커밋은 `타입[적용범위]: 요약`의 `[scope]` 대괄호 형식 엄수 (소괄호 및 마침표 금지).
    3. 인간 개입 지점: AI 에이전트는 PR 생성까지만 수행하며, `develop` 및 `main` 머지 버튼은 사람이 최종 확인 후 직접 클릭.
    4. 독서 기록 관련 RDBMS CRUD 및 데이터 영속화(`record` 스키마)는 `backend-core-api`가 전담 소유(단일 진실 공급원 SSOT)함을 명문화.

## 2026-09-13: develop 브랜치 생성 및 8단계 원자적 커밋/원격 푸시 완료
- **보안 및 민감정보 보호 전수 검증**:
  - `.env` 및 `.env.*` 패턴과 캐시 디렉터리(`.ruff_cache/`, `.mypy_cache/`)를 `.gitignore`에 보완 반영하여 시크릿 유출 원천 차단.
  - 불필요한 `docs/` 디렉터리 삭제.
  - `pyproject.toml`에 `[tool.mypy]` 호환 설정을 적용하여 중앙 CI Mypy 검증 통과 보장.
- **원자적 커밋 및 develop 푸시**:
  - `develop` 브랜치 분기 후 DPYB 커밋 컨벤션(`타입[적용범위]: 요약`)에 맞춰 8단계 분할 커밋 수행:
    1. `chore[project]: 기본 프로젝트 환경 및 빌드/도커 설정 추가`
    2. `feat[database]: Supabase core 및 record 스키마 Alembic 마이그레이션 구성`
    3. `feat[core]: FastAPI 앱 진입점 및 DB/인증/예외 공통 모듈 구현`
    4. `feat[library]: 서재·도서·스크랩 및 사서 도메인 모델/서비스/라우터 구현`
    5. `feat[record]: 독서 감상 기록 및 스크랩 영속화 CRUD 구현`
    6. `test[all]: 44개 도메인 단위 및 API 통합 테스트 스위트 추가`
    7. `ci[github]: 중앙 Reusable 워크플로우 연동 CI/린트 파이프라인 구성`
    8. `docs[harness]: DPYB 개발 하네스 체계 및 서비스 문서화`
  - `origin/develop` 브랜치로 원격 푸시 완료.

## 2026-09-13: 실환경 Supabase 마이그레이션 및 개별 DB 환경변수 지원
- **환경변수 편의성 및 보안 강화**:
  - 비밀번호 내 특수문자(`@`, `%`, `$` 등)로 인한 URL 파싱 오류를 방지하기 위해 `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` 개별 환경변수 및 자동 URL 인코딩 기능 추가 (`app/config.py`).
  - `.env.example`에 개별 환경변수 설정 가이드 반영.
- **asyncpg 다중 DDL 실행 호환성 개선**:
  - Alembic 마이그레이션 스크립트(`001_initial_core_schema.py`, `002_add_record_schema.py`)에서 `asyncpg`의 prepared statement 다중 쿼리 제약 해소를 위해 테이블 및 인덱스/트리거 DDL을 단일 `op.execute` 단위로 분할.
  - `alembic/env.py`에서 `core` 및 `record` 스키마 사전 생성 시 트랜잭션 커밋 보장.
- **클라우드 Supabase DB 마이그레이션 전수 검증**:
  - `alembic upgrade head` 성공: `core` 스키마 6종 테이블, `record` 스키마 2종 테이블, 사서 4종 초기 시드 데이터 정상 적재 확인.

## 2026-09-14: backend-auth 병합 및 Google/Kakao 소셜 로그인 통합 ($0 인프라 최적화)
- **AWS Cognito 완전 걷어내기 및 서비스 병합**:
  - `backend-auth`의 무거운 AWS 의존성(boto3, SRP, Cognito 오류 매핑 약 1,500줄)을 배제하고, 순수 회원 도메인과 소셜 로그인 모듈을 `backend-core-api`로 일원화.
  - Render 무료 티어(월 750시간) 인스턴스 3개 동시 가동 시 10일 만에 소진되던 한계를 극복하기 위해 백엔드를 2개(`core+auth`, `ai-agent`)로 압축하여 15~16일 무료 가동 시간 확보.
- **스키마 및 Alembic 마이그레이션 (`003_add_member_schema.py`)**:
  - `member` 스키마 신설: `member.members`, `member.terms`, `member.member_agreements` 테이블 및 트리거, 인덱스 구축.
  - 기본 약관 3종(`TERMS_OF_SERVICE`, `PRIVACY`, `AI_ANALYSIS`) baseline seed 데이터 적재.
  - 실환경 Supabase DB에 `alembic upgrade head` 성공 반영 (`003_add_member_schema (head)`).
- **소셜 로그인 및 자체 JWT 토큰 체계**:
  - `SocialAuthService`: `httpx` 비동기 클라이언트로 Google `id_token` (tokeninfo API) 및 Kakao `access_token` (/v2/user/me API) 검증 구현.
  - `security.py`: 자체 HS256 Bearer JWT 발급(`create_access_token`, `create_refresh_token`) 및 갱신/검증 구현.
  - `MemberService`: 소셜 로그인 시 신규 회원 자동 가입(Get-or-Create) + 기본 책장(`Default Shelf`) 자동 생성 보장.
  - 회원 탈퇴(`DELETE /api/v1/users/me`) 시 서재 책장, 도서, 스크랩, 독서기록, 사서 데이터를 단일 트랜잭션에서 일괄 소프트 삭제하는 전사 Cascade 처리 구현.
- **테스트 및 검증**:
  - 신규 소셜 로그인, 토큰 갱신, 중복 확인, 프로필 조회/수정, 탈퇴 Cascade, 약관 동의/철회 테스트 6건 추가.
  - 총 50개 테스트 100% 통과 및 `ruff check`, `ruff format`, `mypy` 검증 완료.

**다음 세션 시작 시**:
1. Render Web Service 컨테이너 배포 및 환경변수 등록 (`DB_USER`, `DB_PASSWORD`, `JWT_SECRET_KEY`, `CORS_ORIGINS` 등).
2. 중앙 `DPYB/.github` 킵얼라이브 워크플로우에 등록된 Core API 엔드포인트(`https://<app>.onrender.com/health`) 핑 수신 확인.
3. `backend-ai-agent` 서버와의 사서/토론 모드 Function Calling(Tool) 연동 테스트 진행.

## 2026-09-14: 독서 진도율 자동 동기화 & 국립중앙도서관 API 캐싱/내결함성 강화
- **독서 진도율 및 완독 상태/일시(completed_at) 자동 동기화 (TDD)**:
  - `core.library_book`에 `completed_at TIMESTAMPTZ NULL` 컬럼 추가 (Alembic `004_add_completed_at_to_library_book.py`).
  - `LibraryBook` 모델 및 응답 DTO(`UpdateProgressResponse`, `LibraryBookDetailResponse`, `LibraryBookItemResponse`, `UpdateLibraryBookResponse`, `CreateLibraryBookResponse`)에 `completed_at` 필드 반영.
  - 진도율 수정(`PATCH /progress`) 및 도서 수정(`PATCH /{book_id}`) 시 `current_page == total_pages` 도달 시 `reading_status`를 `COMPLETED`로 자동 전이하고 `completed_at` 현재 시각 기록.
  - 페이지 수 감소 시 `reading_status`를 `READING`으로 자동 복귀 및 `completed_at = None` 리셋 불변식 구현.
- **국립중앙도서관 API 인메모리 TTL 캐싱 & Graceful Fallback (TDD)**:
  - `NationalLibraryClient`: 정제된 ISBN 기반 인메모리 TTL 캐시(`_cache: dict[str, tuple[ExternalBook | None, float]]`) 도입 (정상 도서 24시간, 미존재 도서 1시간).
  - 외부 타임아웃(`httpx.TimeoutException`), 네트워크 단절(`httpx.RequestError`), 외부 5xx 오류 시 500 크래시 없이 경고 로그 후 `None` 반환 및 검색 API 200 OK + `book: None` graceful fallback 보장.
- **테스트 및 코드 품질**:
  - TDD 신규 단위/통합 테스트 7건 추가 (`tests/test_books.py` 4건, `tests/test_search.py` 3건).
  - 총 58개 테스트 100% 통과 (소요시간 1.34s) 및 `ruff check`, `ruff format`, `mypy app` 검증 완료.

**다음 세션 시작 시**:
1. 실환경 Render Web Service 컨테이너 배포 및 Supabase 마이그레이션 (`alembic upgrade head`) 확인.
2. `backend-ai-agent` 서비스와의 Function Calling 연동 테스트.

## 2026-09-14: DPYB 조직 PR 템플릿 미니멀 Type B 다이어트 및 완전 중앙화
- **공통 PR 템플릿 다이어트 (`DPYB/.github`)**:
  - 기존 7개 섹션(스크린샷, 분절된 개요, 6개 체크박스)의 과도한 템플릿을 **Type B 구조**(작업 요약, 적용 범위, 바이브 코딩 고려사항/리뷰포인트, 필수 체크리스트 2개)로 슬림화.
  - 백엔드 불필요 요소(스크린샷) 및 CI 자동 검증 중복 항목(린트/테스트 수동 체크) 제거, `Closes #` 자동 이슈 닫기 보존.
  - 바이브 코딩 시 AI 생성 코드의 사이드 이펙트 복기 및 리뷰 집중 지점을 짚어줄 수 있도록 `💬 고려사항 & 리뷰 포인트 (선택)` 섹션 보강.
  - `DPYB/.github` 메인 브랜치에 커밋 및 원격 푸시 완료.
- **전사 3개 레포(`frontend-reader-web`, `backend-core-api`, `backend-ai-agent`) 완전 중앙화 상속**:
  - `backend-core-api` 내 기존 중복 파일(`.github/pull_request_template.md`)을 `git rm`으로 삭제 및 `origin/develop`에 푸시.
  - DPYB 조직 내 3개 전체 레포가 `DPYB/.github`의 공통 템플릿을 자동으로 참조하도록 단일 진실 공급원(SSOT) 확립 완료 (`gh api repos/.../community/profile` 검증 완료).

## 2026-09-14: 프론트엔드 연동용 개발자 간편 로그인 & 쿠키 세션 호환 지원
- **프론트엔드(`frontend-reader-web`) 원격 코드베이스 심층 분석**:
  - 로컬 클론 없이 GitHub CLI/API로 프론트엔드 인증 구조(`LoginPage.jsx`, `authApi.js`, `AuthProvider.jsx`) 조회.
  - 프론트엔드가 이메일/비번 폼 기반 `POST /api/v1/auth/login` 및 `authFetch`의 쿠키 기반 토큰 갱신(`POST /api/v1/auth/refresh`)을 호출하고 있음을 확인.
- **개발자 간편 로그인 및 토큰 직렬화 호환**:
  - `POST /api/v1/auth/login`: 이메일 기반 자동 가입(Get-or-Create), 기본 책장 및 기본 대표 고양이 사서(`CAT`, "블루", Lv.1) 자동 지급.
  - `TokenResponse`: 프론트엔드 JS 호환을 위해 `@computed_field`를 통해 camelCase(`accessToken`, `refreshToken`)와 snake_case(`access_token`, `refresh_token`) 듀얼 직렬화 지원.
  - `LoginResponse`: 프론트엔드 전역 상태(`AuthProvider`) 즉시 동기화를 위한 `member` 프로필 정보 포함.
- **HttpOnly 쿠키 기반 세션 복원 및 CORS 개선**:
  - `/login`, `/social/google`, `/social/kakao`, `/refresh`에서 `Set-Cookie: refresh_token=...; HttpOnly; SameSite=Lax` 발행.
  - `POST /refresh`: Body 또는 Cookie 듀얼 수신을 지원하여 페이지 새로고침 시에도 세션 자동 복원 보장.
  - `POST /logout`: `refresh_token` 쿠키 삭제(`Max-Age=0`).
  - `CORSMiddleware`: 로컬 개발 프론트엔드 포트(5173, 3000 등) 대응 `allow_origin_regex` 추가.
- **테스트 및 코드 품질**:
  - 신규 통합 테스트 3건 추가 (`tests/test_social_auth_and_members.py`), 총 61개 테스트 100% Pass (소요시간 1.54s).
  - `ruff check`, `ruff format`, `mypy app` 린트/타입 검증 완료.

**다음 세션 시작 시**:
1. 로컬 환경에서 `backend-core-api`(8000), `backend-ai-agent`(8001) 구동 후 `frontend-reader-web` E2E 연동 확인.
2. Render Web Service 컨테이너 배포 및 Supabase 마이그레이션 적용.

## 2026-09-14: DPYB 전사 레포 Squash 머지 단일화 및 원클릭 커밋 자동화
- **전사 레포 머지 전략 일괄 적용 (`gh api`)**:
  - DPYB 조직 산하 4개 전체 레포(`backend-core-api`, `backend-ai-agent`, `frontend-reader-web`, `.github`) 대상 API 일괄 패치 적용 완료:
    1. `allow_merge_commit: false`: 불필요한 머지 커밋 옵션 원천 차단.
    2. `allow_rebase_merge: false`: 리베이스 머지 차단.
    3. `allow_squash_merge: true`: Squash and merge 단일화.
    4. `squash_merge_commit_title: "PR_TITLE"`: PR 제목(`타입[적용범위]: 요약`)이 커밋 제목으로 100% 자동 매핑.
    5. `squash_merge_commit_message: "BLANK"`: Extended description 본문은 기본 빈칸으로 자동 생성 (불필요한 작업 커밋 덤프 방지).
    6. `delete_branch_on_merge: true`: 머지 완료 시 피처 브랜치 원격 자동 삭제.
- **DPYB 공통 표준 및 스크립트 반영 (`DPYB/.github`)**:
  - `docs/02-git-conventions.md`: Squash and merge 단일화 및 자동 커밋 매핑/본문 빈칸 머지 전략 명문화.
  - `.github/scripts/setup-branch-protection.sh`: 레포지토리 전역 머지 전략 설정 단계 추가 반영 및 커밋/푸시 완료 (`d8439af`).
- **개발자 경험 개선**:
  - 머지 시 수동 텍스트 복사/편집 없이 **내용 확인 후 [Confirm squash and merge] 클릭 1회**로 DPYB 커밋 컨벤션 자동 준수 완성.

## 2026-09-15: DPYB 중앙 PR 린트 및 템플릿에 '고려사항' 필수 검증 로직 반영
- **중앙 CI 워크플로우 보강 (`DPYB/.github/.github/workflows/reusable-pr-lint.yml`)**:
  - `## 💬 고려사항 & 리뷰 포인트` 섹션을 필수 4대 섹션으로 승격 및 자동 검사 항목에 추가.
  - 고려사항 섹션의 본문이 주석이나 빈 불릿(`- `) 형태로만 방치되는 경우를 검출하여 PR 차단.
  - 특별한 고려사항이 없는 단순 작업 PR의 경우 `해당 없음`, `특이사항 없음`, `N/A` 등을 작성하면 유연하게 통과하도록 설계.
- **공통 템플릿 및 가이드 문서 동기화**:
  - `.github/pull_request_template.md`: 고려사항 주석 가이드에 `(없을 경우 '해당 없음' 또는 '특이사항 없음' 기재)` 안내 추가.
  - `docs/02-git-conventions.md`, `docs/03-vibe-coding-harness.md`: 4대 필수 섹션 명시 및 바이브 코딩 리뷰 포인트 작성 지침 개정.
  - `DPYB/.github` 메인 브랜치에 커밋 및 원격 푸시 완료 (`da5ae49`).

## 2026-09-15: KDC 세부 주제 파서 및 교보문고 CDN 표지 폴백 강화
- **KDC 세부 주제(`subject`) 및 전천후 스마트 장르 파서 (`app/core/kdc_mapper.py`)**:
  - 국립중앙도서관 API의 광범위한 10대 대분류(문학 등) 대신 소수점 세부분류기호(예: `813.7` -> `SF/과학소설`, `818` -> `에세이/산문`, `005.133` -> `IT/프로그래밍` 등)로부터 직관적인 세부 주제를 도출하는 `kdc_to_subject` 매퍼 구현.
  - AI 에이전트와 프론트엔드의 국문("SF", "에세이", "문학", "철학"), 영문 대소문자("literature", "philosophy"), 레거시 코드("LITERARY_FICTION", "SCIENCE_FICTION"), 숫자 분류기호("813.7") 입력을 모두 자동 인식하여 표준 `GenreType` 대분류와 세부 `subject`로 분리 변환하는 `parse_to_genre_and_subject` 구현.
- **도서 등록/수정 DTO 유연화 및 화면 표시 필드 (`app/schemas/library_book.py`, `app/schemas/search.py`)**:
  - `CreateLibraryBookRequest`, `UpdateLibraryBookRequest`에 `@model_validator(mode="before")`를 적용하여 `genre` 및 `subject` 자동 파싱 및 보완.
  - 모든 도서 응답 DTO(`CreateLibraryBookResponse`, `LibraryBookItemResponse`, `LibraryBookDetailResponse`, `UpdateLibraryBookResponse`, `ExternalBook`, `SearchLibraryBookDetail`)에 `@computed_field display_genre` 추가 (`self.subject or self.genre_name` 계층형 폴백).
- **국립중앙도서관 클라이언트 및 도서 서비스 교보문고 고화질 CDN 표지 폴백 (`app/services/national_library.py`, `app/services/book_service.py`)**:
  - `get_verified_cover_url`: 도서관 서지정보 표지 URL이 누락되더라도 정제된 10자리/13자리 ISBN이 있을 경우 교보문고 고화질 CDN(`contents.kyobobook.co.kr`)으로 0ms 즉시 결합 폴백.
  - 도서 검색(`lookup_by_isbn`) 및 도서 생성/수정(`create_book`, `update_book`) 시에도 클라이언트 표지 누락 시 ISBN 기반 교보문고 CDN 자동 보완 적용.
- **테스트 및 품질 검증**:
  - `test_kdc_mapper.py` (KDC 세부 주제 및 스마트 파싱 단위 테스트 4건 추가), `test_books.py` (한글/영문/세부장르 등록 및 표지 자동 주입 테스트 2건 추가), `test_search.py` (교보문고 CDN 폴백 및 세부주제 통합 테스트 1건 추가).
  - 총 67개 단위/통합 테스트 100% Pass (1.83s), `ruff check`, `ruff format`, `mypy app` 린트/타입 검사 100% 무결점 통과.
- **머지 및 브랜치 정리**:
  - PR [#6](https://github.com/DPYB/backend-core-api/pull/6) squash and merge 완료 (`324c30a`), `origin/develop` 동기화 및 로컬 피처 브랜치 정리 완료.

**다음 세션 시작 시**:
1. **로컬 풀스택 E2E 연동 검증** (`.harness/PLAN.md` 1번):
   - `backend-core-api` (포트 8000) 구동
   - `backend-ai-agent` (포트 8001, `CORE_API_BASE_URL=http://127.0.0.1:8000`) 구동
   - `frontend-reader-web` 개발 서버 연동: 로그인 -> 3D 서재 -> 사서 추천 도서 클릭 및 `displayGenre`/표지 이미지 자동 채움 등록 E2E 검증
2. **실환경 인프라 배포 및 무과금($0) 상시 가동 검증** (`.harness/PLAN.md` 2번):
   - Render Web Service 신규 배포 및 환경변수 등록, Supabase 마이그레이션 확인, 중앙 킵얼라이브 연동 점검.

## 2026-09-15: 사서 월간 독서 리포트 통계 집계 API & 스톱워치 독서 세션 구축
- **기획 요구사항 분석 및 불필요한 '중단' 상태 배제**:
  - `BookReadingStatus`에 '중단' 상태를 새로 추가하지 않고 기존 3단계 체제(`PLANNED`, `READING`, `COMPLETED`)를 유지하여 시스템 복잡도 최소화. 리포트 05번 항목은 "완독 도서 / 읽는 중 도서"로 일원화.
- **날씨 데이터 및 스톱워치 세션 모델 영속화 (`005_add_reading_session_and_weather.py`)**:
  - `record.records` 테이블에 `weather VARCHAR(50) NULL` 컬럼 추가 (프론트엔드 Geolocation 기반 condition 자연 수집).
  - `record.reading_sessions` 테이블 신설: `id`, `member_id`, `book_id` (옵셔널/자유독서), `duration_minutes`, `start_page`, `end_page`, `weather`, `created_at`.
- **스톱워치 독서 세션 기록 API (`POST /api/v1/reading-sessions`)**:
  - 스톱워치 종료 시 단 1회 호출로 소요시간(분), 페이지 증분, 날씨를 영속화.
  - 도서가 지정된 경우 `book.current_page` 갱신 및 100% 도달 시 `COMPLETED` 자동 전이/`completed_at` 자동 기록.
- **월간 독서 리포트 정량 통계 집계 서비스 및 API (`GET /api/v1/reports/monthly-stats`)**:
  - `ReportService`: 01~05번 전수 정량 통계 집계 (사서 정보, 완독수/누적페이지/총독서시간/목표달성률, 요일/시간대/날씨 활동 분포, 평균 완독일, 최장 연속 독서 Streak, KDC 10대 장르 점유율 및 편독/다양성 지수, 상위 스크랩 도서, 대표 감상평, 완독/읽는중 도서 목록).
  - 프론트엔드와 AI 에이전트 연동 호환을 위해 모든 DTO를 `CamelModel` 상속으로 camelCase 자동 직렬화 및 mypy 무결점 타입 보장.
- **테스트 및 품질 검증**:
  - `tests/test_reading_sessions.py` 5건, `tests/test_monthly_reports.py` 2건 추가 (총 74개 테스트 100% Pass).
  - `ruff check`, `ruff format`, `mypy app` 린트/타입 검사 100% 무결점 통과.

**다음 세션 시작 시**:
1. AI 에이전트 서비스(`backend-ai-agent`)에서 Core API의 `GET /api/v1/reports/monthly-stats` 연동 및 Gemini LLM 프롬프트(06번 성향 분석, 07번 독서 처방) 파이프라인 구현.
2. 프론트엔드(`frontend-reader-web`)에서 스톱워치 모달(`POST /api/v1/reading-sessions`) 및 월간 리포트 뷰/PDF 다운로드 연동.
3. 로컬 풀스택 E2E 연동 검증 및 Render 배포.

## 2026-09-15: 동물 사서 4종 페르소나 및 기본 표시명 동기화 (`SEA_SLUG` ➔ '누디')
- **사서 4종 페르소나 카탈로그 및 기본 표시명 동기화 (`app/models/enums.py`)**:
  - `backend-ai-agent` 명세서에 맞춰 `SEA_SLUG`의 기본 표시명을 기존 '바다달팽이'에서 '누디'로 개편.
  - 사서 4종 메타데이터 카탈로그(`LIBRARIAN_METADATA`) 및 기본 표시명 매핑(`DEFAULT_LIBRARIAN_NAMES`) 구축:
    1. `CAT`: 러시안 블루, 기본 표시명 "블루", MBTI INTJ, 담당 장르 [총류, 철학, 종교], 종결어미 ~냥
    2. `SHOEBILL`: 넙적부리황새, 기본 표시명 "슈빌", MBTI ISTP, 담당 장르 [자연과학, 기술과학], 종결어미 ~두둥
    3. `SEA_SLUG`: 갯민숭달팽이, 기본 표시명 "누디", MBTI INFP, 담당 장르 [예술, 문학], 종결어미 ~누누
    4. `GECKO`: 게코 도마뱀, 기본 표시명 "게코", MBTI ENFJ, 담당 장르 [사회과학, 언어, 역사], 종결어미 ~크크
- **사서 타입 조회 & 획득 API 개선 (`app/schemas/librarian.py`, `app/services/librarian_service.py`)**:
  - `GET /api/v1/librarian-types`: 응답 DTO에 `default_name`, `species`, `mbti`, `genres`, `description`, `ending_style`을 기본 제공하여 프론트엔드가 하드코딩 없이 사서 정보를 동적 렌더링하도록 지원.
  - `POST /api/v1/librarians`: `name` 필드를 옵셔널로 변경하여 생략/공백 시 타입별 `default_name` 자동 지정 (예: `SEA_SLUG` -> "누디").
  - 대표 사서 및 내 사서 목록 조회 시 메타데이터 필드 함께 반환.
- **회원 프로필 조회 API 사서 정보 통합 & 라우터 별칭 (`app/schemas/member.py`, `app/services/member_service.py`, `app/routers/users.py`)**:
  - `MemberProfileResponse`에 `librarian_type`, `librarian_name`, `librarian_default_name` 필드 추가.
  - `GET /api/v1/users/me` 및 프론트엔드 연동용 별칭 `GET /api/v1/members/me` 지원.
  - 월간 리포트 통계 집계(`ReportService`) 사서 이름 폴백 보강.
- **테스트 및 코드 품질 검증**:
  - `tests/test_librarians.py`: 사서 4종 페르소나 메타데이터 검증, `SEA_SLUG` 이름 생략 획득 시 "누디" 자동 지정, 프로필 조회 시 사서 정보 동기화 및 `/api/v1/members/me` 별칭 검증 3개 테스트 추가.
  - 총 77개 테스트 100% Pass (1.86s), `ruff check`, `ruff format`, `mypy app` 검사 100% 무결점 통과.

**다음 세션 시작 시**:
1. AI 에이전트 서비스(`backend-ai-agent`)에서 Core API `GET /api/v1/reports/monthly-stats` 연동 및 Gemini LLM 분석/처방 구현.
2. 프론트엔드(`frontend-reader-web`)에서 스톱워치 모달(`POST /api/v1/reading-sessions`) 및 월간 리포트 뷰/PDF 다운로드 연동.
3. 로컬 풀스택 E2E 연동 검증 (`.harness/PLAN.md` 1번) 및 Render 배포.

## 2026-09-16: 타 서비스(Frontend/AI Agent) 통신 계약 완벽 일치화 & 소셜 로그인 실환경 스펙 확정
- **타 서비스 통신 계약 전수 분석 및 페이징 응답 듀얼 직렬화 (`app/schemas/common.py`, `app/schemas/library_book.py`, `app/schemas/scrap.py`)**:
  - `frontend-reader-web`의 `listLibraryBooks()`가 `res.books`, `listScraps()`가 `res.scraps`를 기대하고, `backend-ai-agent`는 `res.items`를 조회하는 불일치를 발굴 및 해결.
  - `LibraryBookPageResponse` 및 `ScrapPageResponse`를 구현하여 `@computed_field`를 통해 `items`, `books`, `scraps`를 모두 제공하는 완벽한 하위/상위 호환성 확보.
- **도서 검색 및 단건 상세 조회 유연화 (`app/routers/search.py`, `app/services/book_service.py`, `app/core/security.py`)**:
  - AI 에이전트의 단건 도서 조회(`core_api_client.get_book_details`)를 위해 `GET /api/v1/books/{book_id}` 별칭 라우트 및 `get_book_detail_optional_member` 구현.
  - 도서 검색(`GET /api/v1/books/search`): `isbn` 단건 검색과 `query` 키워드 검색을 모두 수용하고 `get_optional_member_id`를 통해 비로그인/도구 호출 허용. 응답 DTO `BookSearchResponse`에 AI 에이전트 호환용 `books` 리스트 자동 구성.
- **소셜 로그인 프로필 즉시 반환 (`app/routers/auth.py`)**:
  - `/social/google`, `/social/kakao` 응답 모델을 `LoginResponse`로 격상하여 JWT 토큰과 함께 회원 프로필(`member`) 및 대표 사서 정보를 즉시 반환하도록 개선 (프론트엔드 `AuthProvider` 즉시 동기화).
- **실환경 환경변수 템플릿 전면 정비 (`.env.example`)**:
  - Google OAuth 2.0 Web Client ID(`GOOGLE_CLIENT_ID`), Kakao REST API Key(`KAKAO_CLIENT_ID`), Supabase 트랜잭션 풀러(`DB_*`), JWT, 국립중앙도서관, AI Agent 연동 주소, Cloudflare 프론트엔드 CORS 도메인 등 Render 배포용 가이드 완성.
- **전체 서비스 검증 통과**:
  - `backend-core-api`: 신규 테스트 4건 추가, 총 81개 테스트 100% Pass (2.01s), `ruff check`, `ruff format`, `mypy app` 무결점.
  - `backend-ai-agent`: 총 100개 테스트 100% Pass (37.31s).
  - `frontend-reader-web`: `npm run build` 번들 빌드 100% 성공.

**다음 세션 시작 시**:
1. Render Web Service 신규 생성 및 Dockerfile 기반 배포 설정 (동적 `$PORT` 바인딩).
2. Render 대시보드에 확정된 환경변수(`DB_*`, `JWT_SECRET_KEY`, `GOOGLE_CLIENT_ID`, `KAKAO_CLIENT_ID`, `CORS_ORIGINS`, `NL_API_CERT_KEY`) 등록 및 배포.
3. 실환경 배포 인스턴스 헬스체크 (`GET /health`) 및 중앙 `DPYB/.github` 킵얼라이브 워크플로우 핑 수신 확인.

---

## 2026-09-17: KDC 제6판 문학(800) 표준 교정 및 SF 소설 키워드 스마트 오버라이드
- **진행한 작업**:
  - `app/core/kdc_mapper.py`: DDC 서양식 문학 분류가 섞여 있던 `KDC_SUBJECT_MAPPING` 800번대를 한국도서관협회 KDC 제6판 기준(810 한국, 820 중국, 830 일본, 840 영미, 850 독일, 860 프랑스, 870 스페인, 880 이탈리아, 890 기타)으로 전면 교정. 《마션》(843)이 프랑스문학으로 오역되던 버그 해결.
  - `refine_subject_by_keywords`: 외국 소설에 대해 세부 장르 번호를 부여하지 않는 KDC의 한계를 극복하기 위해, 도서 제목 및 설명에서 SF 키워드(`SF`, `과학소설`, `우주`, `외계`, `화성`, `사이언스 픽션` 등)를 검사하여 `SF/과학소설`로 자동 보정 및 대분류 승격하는 스마트 오버라이드 로직 구현.
  - `app/services/national_library.py`: 국립중앙도서관 API 서지정보 파싱 시 도서 제목/설명 기반 `refine_subject_by_keywords` 오버라이드 적용.
  - `app/schemas/library_book.py`: 서재 도서 등록(`CreateLibraryBookRequest`) 및 수정(`UpdateLibraryBookRequest`) 모델 검증기에서 도서 제목(`title`)을 연동하여 SF 키워드 오버라이드 자동 반영.
  - `tests/test_kdc_mapper.py`, `tests/test_search.py`: KDC 843(영미소설), 820(중국), 830(일본) 매핑 및 《마션》 실서지 데이터 검색 시 `SF/과학소설`로 보정되는 단위/통합 테스트 추가.
  - 총 83개 단위/통합 테스트 100% 통과 및 `ruff check` 0 에러 검증.
- **다음 세션에서 할 일**:
  - 실환경 Render 배포 및 E2E 브라우저 최종 스모크 테스트.

## 2026-09-17: 화면 노출 우선순위 Subject 1순위 전면 보장 및 510번대 치료/건강 라우팅 보강
- **진행한 작업**:
  - `app/schemas/library_book.py`, `app/schemas/search.py`: 프론트엔드가 `genreName`을 직접 참조하든 `displayGenre`를 참조하든 상관없이, 세부 주제(`subject`)가 존재할 경우 최우선으로 반환하도록 DTO 레벨 2중 방어 조치 구현.
  - `app/core/kdc_mapper.py`: KDC 513.8(미술치료/심리요법) 및 51(건강/의학) 매핑 보강, `THERAPY_KEYWORDS`("미술치료", "그림의 힘", "심리치료", "마음치유", "예술치료") 스마트 오버라이드 및 PHILOSOPHY 승격 연동.
  - `app/main.py`: 콘솔(stdout) 및 10MB 크기 회전 파일(`logs/app.log`) 듀얼 로깅 파이프라인 구축 및 Uvicorn 로거 통합.
  - `tests/test_books.py`, `tests/test_search.py`, `tests/test_kdc_mapper.py`: 세부 주제 우선순위 반영 및 신규 매핑/키워드 검증 테스트 갱신 완료.
  - 단위/통합 테스트 83개 100% 통과 (소요시간 2.14s), `ruff check`, `mypy app` 검사 100% 무결점 통과.
- **다음 세션에서 할 일**:
  - Render Web Service 배포 및 실환경 헬스체크 연동 검증.

## 2026-09-17: 독서 기록 라우터 인증 의존성 표준화 (JWT & X-Member-Id 듀얼 지원)
- **진행한 작업**:
  - `app/routers/records.py`: 하드코딩된 필수 `Header(..., alias="X-Member-Id")` 주입 방식을 전역 표준인 `Depends(get_authenticated_member_id)`로 전면 교체. 이를 통해 Bearer JWT 토큰과 `X-Member-Id` 헤더를 모두 수용하고 `AUTH_DISABLED` 테스트 환경에서도 일관되게 동작하도록 보장.
  - `tests/test_records.py`: 의존성 통일에 따른 인증 테스트 케이스 최신화 (`AUTH_DISABLED` 테스트 환경 자동 인증 대응).
  - 총 83개 단위/통합 테스트 100% 통과 및 `ruff check` 검증 완료.
- **다음 세션에서 할 일**:
  - Render 배포 및 실환경 E2E 점검.








