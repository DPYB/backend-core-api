# AGENTS.md — 개발 하네스 지침

> DPYB `backend-core-api` 서비스 레포지토리의 AI 코딩 에이전트(Antigravity, Claude Code, Codex, Kiro 등) 공용 워크플로우 및 개발 규칙집입니다.

---

## 1. 세션 시작 시 필수 읽기 순서
어떤 AI 도구로 세션을 시작하든 아래 5대 파일만 읽고 동기화한다 (`.harness/archive/`는 직접 읽지 말고, 필요 시 grep으로만 조회):
1. `.harness/HANDOFF.md` — 직전 세션 인수인계 (최대 200줄)
2. `.harness/STATE.md` — 지금까지 무엇이 완료되었는지 스냅샷 (최대 150줄)
3. `.harness/ARCHITECTURE.md` — 기술 스택/폴더 구조/컨벤션 SSOT
4. `.harness/PLAN.md` — 현재 진행 중인 본 레포 계획
5. `.harness/DECISIONS.md` — 핵심 결정 히스토리 (3단 압축)
(필요 시 `.harness/BACKLOG.md` 미해결 부채 참조)

---

## 2. 문서별 책임 (중복 기록 금지)

| 문서 | 반드시 담아야 하는 내용 (단일 소유) | 절대 담지 말아야 하는 내용 |
| :--- | :--- | :--- |
| **`HANDOFF.md`** | **최대 5개 세션 & 최대 200줄 상한**의 작업 흐름 및 다음 세션 인수인계 로그 (초과분은 `.harness/archive/` 보관) | 단계별 완료 요약(`STATE` 몫), 결정 이유(`DECISIONS` 몫), **타 레포 내부 작업/코드** |
| **`STATE.md`** | **최대 150줄 상한**의 마일스톤 단위 간결한 완료 스냅샷 (1~3줄 요약) | 세션별 서술(`HANDOFF` 몫), 상세 diff/PR 전문 장황한 나열, **타 레포 구현 내역** |
| **`ARCHITECTURE.md`** | 지금 시점의 기술 스택/폴더 구조/컨벤션 (현재 상태, 항상 덮어쓰기) | 왜 그렇게 정했는지(`DECISIONS` 몫), 진행 중인 계획(`PLAN` 몫) |
| **`DECISIONS.md`** | **최대 150줄 & 최대 20KB 상한**의 결정 내용과 이유의 역사 (최신순 append-only). [결정/이유/영향] 3단 압축 구조 준수 | 단순 구현 여부나 진행 상황(`STATE` 몫). 폐기된 결정은 삭제 대신 `[Superseded by ...]` 링크 1줄로 보존 |
| **`PLAN.md`** | 본 레포에서 아직 안 끝난 계획과 체크리스트만 | 완료된 항목(`STATE`로 이동), **타 레포 전용 구현 태스크** |
| **`BACKLOG.md`** | 지금 하지 않지만 나중에 할 것 (버그, 기술부채, 아이디어) | 현재 진행 중인 계획(`PLAN` 몫) |

---

## 3. 작업 워크플로우 (필수)

- **레포지토리 경계 엄수 (Cross-Repo Isolation)**: 본 레포 하네스에는 **본 레포(`backend-core-api`) 코드베이스와 직접 관련된 내용만 기록**한다. 타 레포(frontend, ai-agent 등)와 연계된 작업은 해당 레포의 하네스에 기록하며, 본 레포에서는 "타 레포 PR 링크" 또는 "API 인터페이스 규격 1줄"로만 참조한다.
- **`HANDOFF.md` 엄격한 롤링 (5세션 & 200줄 상한)**: `HANDOFF.md` 본문에는 **세션 수 최대 5개, 전체 라인 수 최대 200줄**만 유지한다. 기준 초과 시 가장 오래된 세션부터 `.harness/archive/HANDOFF_YYYY-MM.md`로 이동 보관한다. (동일 월에 추가 롤링 발생 시 새 파일을 만들지 않고 기존 월 파일에 이어붙인다).
- **아카이브 파일명 표준 규격**: `archive/` 디렉토리 내 파일명은 반드시 **`^(HANDOFF|STATE|DECISIONS)_\d{4}-\d{2}\.md$`** (예: `HANDOFF_2026-09.md`, `STATE_2026-09.md`) ISO 하이픈 표준을 준수한다.
- **Phase(기능)와 Session(작업) 번호 분리**:
  - **`세션 N` 또는 날짜 헤더**: `HANDOFF.md` 전용 작업자 턴/인수인계 시간축 로그 (`## YYYY-MM-DD: 작업명` 또는 `## 세션 N`).
  - **`Phase N`**: `PLAN.md` 및 `STATE.md` 전용 기능 마일스톤 단위. **세션 번호와 연동하지 않으며**, 하나의 Phase가 여러 세션에 걸치거나 한 세션에 일부만 진행될 수 있다.
- **하네스 규격 자동 검증**: 커밋/PR 전 `python3 scripts/check_harness.py`를 실행하여 라인 수 상한, 아카이브 파일명 규칙, 타 레포 오염 여부를 기계적으로 검증한다.
- **계획 수립 우선**: 새로운 기능/변경 요청을 받으면 바로 코드를 고치지 말고 `.harness/PLAN.md`에 계획 초안을 작성해 사용자에게 제시한다. (단순 질의응답, 사소한 오탈자 수정은 계획 없이 바로 가능)
- **사용자 승인 후 구현**: 사용자가 명시적으로 컨펌하면 구현을 시작한다. 구현 방식(TDD 등)은 이 레포 특성에 맞는 사이클을 따르되, "확인 → 구현 → 기록" 순서는 항상 지킨다.
- **점진적 반영**: `PLAN.md`의 세부 체크리스트가 완료될 때마다 즉시 `.harness/STATE.md`에 한 줄로 반영하고 `PLAN.md`에서 제거한다.
- **세션 종료/인수인계**: 작업을 중단하거나 세션을 종료할 때 반드시 `.harness/HANDOFF.md`에 다음 세션을 위한 인수인계 서술을 남긴다.
- **중요 결정 기록**: 아키텍처나 정책의 중요한 결정은 `.harness/DECISIONS.md` 표 최상단에 이유와 함께 기록하며, 폐기된 결정은 삭제하지 않고 `[Superseded by 새 결정]` 링크로 추적성을 보존한다.
- **커밋**: 사용자가 명시적으로 요청했을 때만 수행하며, 변경된 파일만 선별해 스테이징한다 (`git add .` 지양). 커밋 메시지는 `타입[적용범위]: 요약` 형식을 준수한다. 본문(body)이나 머지 시 Extended description은 필수가 아니며, 제목에 없는 새로운 정보(이유, 대안 비교 등)가 있을 때만 작성하고 없으면 비워둔다 (제목 복사 금지).
- **인간 개입 지점 (Human Checkpoint)**: 에이전트는 코드 작성, 테스트, 로컬 검증, 커밋, PR 생성까지만 수행하며, `develop` 및 `main` 머지 버튼은 절대 직접 누르지 않고 사람이 최종 확인 후 클릭한다.

---

## 4. 이 레포 고유 정책 (`backend-core-api`)

- **기술 스택**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (비동기 `asyncpg`), Alembic, pytest
- **DB 스키마 격리 및 데이터 소유권**:
  - 단일 Supabase PostgreSQL DB 내 `core` 스키마(서재, 도서, 스크랩, 사서 4종 마스터 및 회원 소유권) 소유.
  - **독서 기록 관련 RDBMS CRUD 및 데이터 영속화 소유**: `record` 스키마(`records`, `scraps`)의 RDBMS 영속화 및 CRUD를 본 레포(`backend-core-api`)가 전담 소유(단일 진실 공급원 SSOT). AI 에이전트 서비스는 벡터 검색/대화 추론에 집중.
- **Supabase Pooler 호환**: 트랜잭션 풀러(포트 6543) 연동 시 `statement_cache_size=0, prepared_statement_cache_size=0` 필수 적용.
- **도메인 불변식**:
  - **LexoRank (`ShelfRank`)**: 62진수 사전식 순서 문자열 정렬 및 자동 재분배(`rebalanced_sequence`).
  - **KDC 장르 체계**: KDC 10대 대분류 ENUM(`genre`), `@computed_field` 한글명(`genreName`: "문학", "기술과학" 등) 자동 계산, 세부 주제어(`subject`), 상세 분류기호(`kdc`).
  - **사서(Librarian) 4종**: `CAT`(블루), `SHOEBILL`(슈빌), `SEA_SLUG`(누디 - 갯민숭달팽이), `GECKO`(게코) (레거시 `RUSSIAN_BLUE` 별칭 호환). 회원당 타입별 최대 1마리, 단일 대표 사서 유지.
  - **도서 및 스크랩 Soft Delete Cascade**: 도서 또는 독서 기록 삭제 시 소속된 스크랩 일괄 소프트 삭제 (`deleted_at = now()`).
  - **Default Shelf 보장**: 회원당 기본 책장 자동 생성(Get-or-Create) 및 삭제 불가(`DEFAULT_SHELF_CANNOT_BE_DELETED`). 책장 삭제 시 소속 도서는 기본 책장 맨 뒤로 자동 이관.
- **인증 계약**:
  - 오직 서명된 Bearer JWT 토큰만을 검증 (`sub` 또는 `member_id` → `UUID` 변환 및 서명/만료 검증).
  - 보안상 `X-Member-Id` 헤더 우회는 원천 금지되며, 미인증 또는 위조 헤더 단독 요청은 `401 Unauthorized`로 차단.
- **에러 응답 규격**: 모든 예외는 전역 핸들러를 통해 일관되게 `{"code": "ERROR_CODE", "message": "설명"}` 형태로 반환 (18종 카탈로그 준수).
- **무과금 배포 정책 ($0)**:
  - Google Cloud Run(서울 리전) + Supabase(PostgreSQL) + Cloudflare(DNS/CDN) 구조 활용.
  - 동적 `$PORT` 환경변수 바인딩 (`Dockerfile`).
  - `/health` 엔드포인트에서 Supabase `SELECT 1`을 수행하여 Supabase(7일 무쿼리 비활성화) 슬립을 1회 호출로 방지.
  - 중앙 `DPYB/.github` 워크플로우에서 10분 주기로 서비스 전체를 일괄 핑하는 중앙 킵얼라이브 연동 (개별 `keep-alive.yml` 크론 불필요).
- **AI 자가 검증 (계층형 3단계 검증 워크플로우 - 3-Tier Verification)**:
  - **Tier 1 (작업 중 - 초고속 피드백)**:
    - `uv run ruff check .` 및 `uv run ruff format .` (0.2초대 빠른 포맷/린트 검사 및 자동 정렬)
    - 변경된 파일 관련 타깃 단위 테스트만 집중 실행 (예: `uv run pytest tests/test_<module>.py`)
  - **Tier 2 (커밋 & PR 직전 1회 - 로컬 안정성 검사)**:
    - `python3 scripts/check_harness.py` (하네스 규격, 라인 수 상한 및 타 레포 오염 방지 기계적 검증)
    - `uv run ruff format --check .` 및 `uv run ruff check .` (원격 CI 포맷/린트 100% 통과 보장)
    - `uv run mypy .` (정적 타입 체크 무결점 검증)
    - `uv run pytest -m "not integration" -x` (무거운 통합 테스트 제외, 첫 실패 시 즉시 멈춰 빠른 수정)
  - **Tier 3 (원격 CI - 안전망)**:
    - PR 생성 및 푸시 시 GitHub Actions 러너가 전체 회귀(통합 테스트 포함 전수 검사)를 수행하며, Required Check가 develop 머지를 최종 보호함.
- **외부 네트워크 I/O 차단 (Mocking 원칙)**:
  - 단위 테스트에서 외부 HTTP/네트워크 통신(카카오 OAuth, 국립중앙도서관/알라딘 도서 검색, 외부 알림, Supabase Storage 등)이 발생하는 지점은 `unittest.mock`으로 가짜 응답을 주입하여 대기 시간을 0ms로 차단함.
  - 실제 외부 서버/DB를 직접 호출하는 무거운 테스트는 `@pytest.mark.integration` 마커를 부착하여 기본 단위 테스트 스위트에서 분리함.
- **중앙 PR 린터 개행 완화 지원**:
  - DPYB 중앙 레포(`DPYB/.github`)의 PR 린터가 업데이트되어, PR 본문의 `- **목적**:` 및 `- **주요 변경사항**:` 뒤에 다음 줄 개행(`\n`) 후 내용을 작성해도 정상 통과됨.

---

## 5. 브랜치 & 커밋 컨벤션
[DPYB `.github` 레포의 02-git-conventions.md](https://github.com/DPYB/.github/blob/main/docs/02-git-conventions.md)를 따르며, 아래 불변식을 강제한다:
- **브랜치 전략**: `feat/*` 단일 접두사 사용 (`feature/*` 사용 절대 금지). 모든 기능 개발 브랜치는 `develop`을 기본 베이스로 분기하고 머지한다. (예: `feat/shelf-order`, `feat/health-check`)
- **PR 및 커밋 컨벤션**: `타입[적용범위]: 요약` 형식 (`[scope]` 대괄호 필수, 소괄호 `()` 사용 금지, 끝마침표 `.` 사용 금지).
  - 허용 타입: `feat`, `fix`, `refactor`, `chore`, `test`, `docs`, `style`
  - 예시: `feat[shelf]: 기본 책장 자동 생성 불변식 추가`
- **인간 최종 머지 원칙**: 에이전트는 코드 작성/검증/커밋/PR 생성까지만 담당하며, PR 최종 머지(develop 머지, develop -> main 릴리즈 머지)는 반드시 사람이 직접 수행한다.

---

## 6. 배포
[DPYB `.github` 레포의 04-deployment-policy.md](https://github.com/DPYB/.github/blob/main/docs/04-deployment-policy.md)를 따른다.
- PR 머지 후 배포는 `develop`(스테이징/개발환경) 및 `main`(프로덕션 Render Web Service) 브랜치를 기준으로 자동 트리거된다.
