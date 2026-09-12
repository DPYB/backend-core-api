# AGENTS.md — 개발 하네스 지침

## 1. 세션 시작 시 필수 읽기 순서
어떤 AI 도구(Claude Code, Codex, Antigravity, Kiro 등)로 세션을 시작하든 아래 순서대로 먼저 읽는다:
1. `.harness/HANDOFF.md` — 직전 세션이 어디서 멈췄는지
2. `.harness/STATE.md` — 지금까지 무엇이 완료되었는지
3. `.harness/ARCHITECTURE.md` — 기술 스택/폴더 구조/컨벤션
4. `.harness/PLAN.md` — 현재 진행 중이거나 제안된 계획
5. 필요 시 `.harness/DECISIONS.md`(과거 결정 이유), `.harness/BACKLOG.md`(미해결 부채)

## 2. 문서별 책임 (중복 기록 금지)

| 문서 | 담는 내용 (단일 소유) | 담지 않는 내용 |
| :--- | :--- | :--- |
| `HANDOFF.md` | 세션마다 무엇을 했는지 (append-only 서술형 로그) | 단계별 완료 요약(STATE 몫), 결정 이유(DECISIONS 몫) |
| `STATE.md` | 지금까지 끝난 것의 단계 단위 요약 스냅샷 | 세션별 서술(HANDOFF 몫). 이슈 하나하나를 로그처럼 쌓지 않는다 |
| `ARCHITECTURE.md` | 지금의 기술 스택/폴더 구조/컨벤션 (현재 상태) | 왜 그렇게 정했는지(DECISIONS 몫), 진행 상황(STATE 몫) |
| `DECISIONS.md` | 결정 내용과 이유의 역사 (최신 결정이 맨 위로, append-only) | 구현 여부/진행 상황(STATE 몫) |
| `PLAN.md` | 아직 안 끝난 계획과 체크리스트만 | 완료된 항목 (체크만 남기지 말고 STATE로 옮긴 뒤 제거) |
| `BACKLOG.md` | 지금 하지 않지만 나중에 할 것 (버그, 기술부채, 아이디어) | 진행 중인 계획(PLAN 몫) |

## 3. 작업 워크플로우 (필수)

- **계획 수립 우선**: 새로운 기능/변경 요청을 받으면 바로 코드를 고치지 말고 `.harness/PLAN.md`에 계획 초안을 작성해 사용자에게 제시한다. (단순 질의응답, 사소한 오탈자 수정은 계획 없이 바로 가능)
- **사용자 승인 후 구현**: 사용자가 명시적으로 컨펌하면 구현을 시작한다. 구현 방식(TDD 등)은 이 레포 특성에 맞는 사이클을 따르되, "확인 → 구현 → 기록" 순서는 항상 지킨다.
- **점진적 반영**: `PLAN.md`의 세부 체크리스트가 완료될 때마다 즉시 `.harness/STATE.md`에 한 줄로 반영하고 `PLAN.md`에서 제거한다.
- **세션 종료/인수인계**: 작업을 중단하거나 세션을 종료할 때 반드시 `.harness/HANDOFF.md`에 다음 세션을 위한 인수인계 서술을 남긴다.
- **중요 결정 기록**: 아키텍처나 정책의 중요한 결정은 `.harness/DECISIONS.md` 표 최상단에 이유와 함께 기록한다.
- **커밋**: 사용자가 명시적으로 요청했을 때만 수행하며, 변경된 파일만 선별해 스테이징한다 (`git add .` 지양). 커밋 메시지는 `타입[적용범위]: 요약` 형식을 준수한다.
- **인간 개입 지점 (Human Checkpoint)**: 에이전트는 코드 작성, 테스트, 로컬 검증, 커밋, PR 생성까지만 수행하며, `develop` 및 `main` 머지 버튼은 절대 직접 누르지 않고 사람이 최종 확인 후 클릭한다.

## 4. 이 레포 고유 정책 (`backend-core-api`)

- **기술 스택**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (비동기 `asyncpg`), Alembic, pytest
- **DB 스키마 격리 및 데이터 소유권**:
  - 단일 Supabase PostgreSQL DB 내 `core` 스키마(서재, 도서, 스크랩, 사서 4종 마스터 및 회원 소유권) 소유.
  - **독서 기록 관련 RDBMS CRUD 및 데이터 영속화 소유**: `record` 스키마(`records`, `scraps`)의 RDBMS 영속화 및 CRUD를 본 레포(`backend-core-api`)가 전담 소유(단일 진실 공급원 SSOT). AI 에이전트 서비스는 벡터 검색/대화 추론에 집중.
- **Supabase Pooler 호환**: 트랜잭션 풀러(포트 6543) 연동 시 `statement_cache_size=0, prepared_statement_cache_size=0` 필수 적용.
- **도메인 불변식**:
  - **LexoRank (`ShelfRank`)**: 62진수 사전식 순서 문자열 정렬 및 자동 재분배(`rebalanced_sequence`).
  - **KDC 장르 체계**: KDC 10대 대분류 ENUM(`genre`), `@computed_field` 한글명(`genreName`: "문학", "기술과학" 등) 자동 계산, 세부 주제어(`subject`), 상세 분류기호(`kdc`).
  - **사서(Librarian) 4종**: `CAT`, `SHOEBILL`, `SEA_SLUG`, `GECKO` (레거시 `RUSSIAN_BLUE` 별칭 호환). 회원당 타입별 최대 1마리, 단일 대표 사서 유지.
  - **도서 및 스크랩 Soft Delete Cascade**: 도서 또는 독서 기록 삭제 시 소속된 스크랩 일괄 소프트 삭제 (`deleted_at = now()`).
  - **Default Shelf 보장**: 회원당 기본 책장 자동 생성(Get-or-Create) 및 삭제 불가(`DEFAULT_SHELF_CANNOT_BE_DELETED`). 책장 삭제 시 소속 도서는 기본 책장 맨 뒤로 자동 이관.
- **인증 계약**:
  - Cognito Access Token 검증 (`token_use == 'access'`, `client_id` 검증, `sub` → `member_id UUID`).
  - 독서 기록 엔드포인트는 `X-Member-Id` 헤더 병행 지원 (누락 시 `422 Unprocessable Entity`).
- **에러 응답 규격**: 모든 예외는 전역 핸들러를 통해 일관되게 `{"code": "ERROR_CODE", "message": "설명"}` 형태로 반환 (18종 카탈로그 준수).
- **무과금 배포 정책 ($0)**:
  - Render(웹서비스) + Supabase(PostgreSQL) + Cloudflare(DNS/CDN) 3단 무료 티어 우선 활용.
  - 동적 `$PORT` 환경변수 바인딩 (`Dockerfile`).
  - `/health` 엔드포인트에서 Supabase `SELECT 1`을 수행하여 Render(15분 인바운드 트래픽)와 Supabase(7일 무쿼리 비활성화) 슬립을 1회 호출로 동시 방지.
  - 중앙 `DPYB/.github` 워크플로우에서 10분 주기로 서비스 전체를 일괄 핑하는 중앙 킵얼라이브 연동 (개별 `keep-alive.yml` 크론 불필요).

## 5. 브랜치 & 커밋 컨벤션
[DPYB `.github` 레포의 02-git-conventions.md](https://github.com/DPYB/.github/blob/main/docs/02-git-conventions.md)를 따르며, 아래 불변식을 강제한다:
- **브랜치 전략**: `feat/*` 단일 접두사 사용 (`feature/*` 사용 절대 금지). 모든 기능 개발 브랜치는 `develop`을 기본 베이스로 분기하고 머지한다. (예: `feat/shelf-order`, `feat/health-check`)
- **PR 및 커밋 컨벤션**: `타입[적용범위]: 요약` 형식 (`[scope]` 대괄호 필수, 소괄호 `()` 사용 금지, 끝마침표 `.` 사용 금지).
  - 허용 타입: `feat`, `fix`, `refactor`, `chore`, `test`, `docs`, `style`
  - 예시: `feat[shelf]: 기본 책장 자동 생성 불변식 추가`
- **인간 최종 머지 원칙**: 에이전트는 코드 작성/검증/커밋/PR 생성까지만 담당하며, PR 최종 머지(develop 머지, develop -> main 릴리즈 머지)는 반드시 사람이 직접 수행한다.

## 6. 배포
[DPYB `.github` 레포의 04-deployment-policy.md](https://github.com/DPYB/.github/blob/main/docs/04-deployment-policy.md)를 따른다.
- PR 머지 후 배포는 `develop`(스테이징/개발환경) 및 `main`(프로덕션 Render Web Service) 브랜치를 기준으로 자동 트리거된다.
