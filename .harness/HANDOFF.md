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


