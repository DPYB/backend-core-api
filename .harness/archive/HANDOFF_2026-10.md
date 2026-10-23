# HANDOFF 아카이브 (2026-10)

## 2026-10-05: 마이페이지 독서 캘린더 월별 활동 단일 최적화 API 신설 및 프론트엔드 연동
- **배경**:
  - 프론트엔드 최신 마이페이지에 독서 캘린더 UI가 추가되었으나, 서재 내 모든 책에 대해 도서별 API 3종을 병렬 호출(N+1 폭탄 요청)하여 렌더링 지연 및 서버 부하를 유발함.
  - 특정 연/월에 해당하는 회원의 독서 활동(세션, 스크랩, 감상기록, 도서 등록)을 단 한 번에 조회하는 단일 최적화 API 신설 및 연동 요청.
- **구현 및 변경 사항**:
  1. **DTO 스키마 정의 (`app/schemas/reading_session.py`)**:
     - `ReadingCalendarActivityItem`: `id`, `date`(KST 기준 `YYYY-MM-DD`), `type`(`TIMER_SESSION`, `SENTENCE_SCRAP`, `READING_RECORD`, `BOOK_REGISTERED`), `title`, `desc`, `memo`, `book_id`, `book_title`, `book_cover_url`, `duration_seconds`, `page_number`, `weather`, `created_at`.
     - `ReadingCalendarResponse`: `year`, `month`, `activities: list[ReadingCalendarActivityItem]`.
  2. **DB 단일 쿼리 최적화 및 타임존 보정 (`app/services/reading_session_service.py`)**:
     - `get_monthly_calendar`: KST(UTC+9) 기준 월초 ~ 월말을 UTC 시각 범위로 변환하여 쿼리함으로써 월초/월말 활동 잘림 오차 원천 방지.
     - `record.reading_sessions`, `core.scrap`, `record.records`, `core.library_book`을 해당 월 범위로 병렬/순차 추출.
     - 도서 메타데이터는 `LibraryBook.id.in_(referenced_book_ids)` 배치 맵으로 매핑하여 N+1 차단.
     - 활동들을 발생 일시(`created_at` 내림차순) 정렬 반환.
  3. **엔드포인트 신설 (`app/routers/reading_sessions.py`)**:
     - `GET /api/v1/reading-sessions/calendar?year={year}&month={month}` (`year`: ge=2020, le=2100 / `month`: ge=1, le=12 / 인증: `Depends(get_current_member_id)`).
  4. **백엔드 단위/통합 테스트 (`tests/test_reading_sessions.py`)**:
     - `test_get_reading_calendar_monthly_activities` 추가: 10월 등록 도서, 세션, 스크랩, 감상문 4종 통합 검증, 9월 데이터 격리 필터링 검증, 타인 데이터 접근 차단 격리 검증 통과.
  5. **프론트엔드 연동 참조**: 프론트엔드 독서 캘린더 단일 호출 연동 (`frontend-reader-web#115` 참조).
  6. **계층형 품질 검증**:
     - 백엔드 Tier 2: `uv run ruff format --check .` (110개 파일 통과), `uv run ruff check .` (0 에러), `uv run mypy .` (100개 파일 무결점), `uv run pytest -m "not integration" -x` (총 124개 테스트 100% 통과, 17.30s).


## 2026-10-06: 공식 데모 계정(DEMO_MEMBER_ID) 도서 및 스크랩 삭제 권한 개방 (Phase 51)
- **배경**:
  - `dpyb@gmail.com` 공식 데모 계정에서 도서 삭제 및 스크랩 삭제 테스트를 직접 수행할 수 있도록 삭제 권한 개방 요청.
  - 비밀번호 변경, 탈퇴, 프로필 수정 등 치명적 파괴 행위는 방어를 유지하면서, 도서/스크랩 삭제 작업만 Allowlist에 안전하게 추가.
- **수행 내용**:
  1. **미들웨어 Allowlist 수정 (`app/main.py`)**:
     - `demo_allowed_write_routes`에 `("DELETE", "/api/v1/library/books/{book_id}")` 및 `("DELETE", "/api/v1/library/scraps/{scrap_id}")` 추가.
  2. **가드 테스트 갱신 (`tests/test_demo_account_guard.py`)**:
     - 데모 계정에서 도서 삭제(204 No Content) 및 스크랩 삭제(204 No Content) 성공 검증 반영.
     - 비밀번호 변경, 회원 탈퇴, 프로필 수정, 임의 책장 생성 등 계정 파괴/탈취 행위의 403 차단 유지 검증.
  3. **3-Tier 검증 통과**:
     - Ruff format & check 100% 무결점.
     - Mypy 정적 타입 체크 100% 무결점.
     - 단위 테스트 124개 전수 통과 (15.93s).
- **다음 세션에서 이어 진행할 작업**:
  1. **게스트 스타터 가이드북(1권) 메타데이터 등록**:
     - 스타터 가이드북 메타데이터 수신 시 `app/services/demo_seed_data.py`의 `GUEST_SEED_BOOKS`에 1권 전용 시드로 등록.
  2. **청소부 크론 주기 단축 및 게스트 리셋 반영**:
     - `.github/workflows/cleanup-demo.yml` 실행 주기를 다회(예: 3~4시간 간격)로 단축 및 `target=all` 리셋 연동.
  3. **프론트엔드 안내 배너 배포 후 게스트 쓰기 활성화**:
     - 프론트엔드 공용 서재 상단 띠배너 배포 확인 후 Cloud Run 환경변수 `ENABLE_GUEST_WRITE=True` 적용.

## 2026-10-06: 도서 발행일자 유연 파싱 및 책장 ShelfRank 동시성 충돌 방어 (Phase 52)
- **배경**:
  - 국립중앙도서관, 알라딘, 서점 API 등에서 `2024`(연도), `2024-05`(연월), `2024.05.01`, `2024/05/01` 등 비표준 문자열 인입 시 422 Unprocessable Entity 에러가 발생하는 문제를 해결.
  - 도서 동시 등록/이관 시 동일한 마지막 책을 읽고 같은 `shelf_rank`를 계산하여 발생할 수 있는 `Key (shelf_id, shelf_rank) already exists` 유니크 제약 충돌 레이스 컨디션을 원천 방어.
- **수행 내용**:
  1. **날짜 파싱 헬퍼 및 DTO 유연성 구현 (`app/core/kdc_mapper.py`, `app/schemas/library_book.py`)**:
     - `parse_to_date(val)` 헬퍼 구현: 다양한 서지 날짜(연도, 연월, 구분자 `.`/`/` 및 8자리 미상 일자)를 안전하게 `date` 객체로 보정하며, 빈 문자열/결측치 인입 시 422 없이 `None`으로 안전 폴백.
     - `CreateLibraryBookRequest`, `UpdateLibraryBookRequest`에 `@field_validator("published_date", mode="before")` 적용.
  2. **`shelf_rank` 동시성 락 & 충돌 재시도 구축 (`app/services/book_service.py`)**:
     - `BookService.create_book` 및 `move_book_shelf`: 대상 책장 조회 시 `with_for_update()` 락 시도로 순번 계산 직렬화.
     - `IntegrityError` 발생 시 `uk_library_book_shelf_rank` 충돌을 감지하여 롤백 후 최신 마지막 책 조회 및 1회 새 rank 계산 재시도(Retry) 구축.
  3. **3-Tier 검증 통과**:
     - `tests/test_kdc_mapper.py` (신규 날짜 파서 전수 검증), `tests/test_books.py` (비표준 발행일자 등록/수정, 랭크 연속성 안전성 검증).
     - 총 128개 단위 테스트 100% 통과 (15.56s), Ruff 및 Mypy 무결점 검증 완료.
- **다음 세션에서 이어 진행할 작업**:
  1. **게스트 스타터 가이드북(1권) 메타데이터 등록**:
     - 스타터 가이드북 메타데이터 수신 시 `app/services/demo_seed_data.py`의 `GUEST_SEED_BOOKS`에 1권 전용 시드로 등록.
  2. **청소부 크론 주기 단축 및 게스트 리셋 반영**:
     - `.github/workflows/cleanup-demo.yml` 실행 주기를 다회(예: 3~4시간 간격)로 단축 및 `target=all` 리셋 연동.
  3. **프론트엔드 안내 배너 배포 후 게스트 쓰기 활성화**:
     - 프론트엔드 공용 서재 상단 띠배너 배포 확인 후 Cloud Run 환경변수 `ENABLE_GUEST_WRITE=True` 적용.


## 2026-10-07: YES24 키워드 검색 기반 도서 탐색 및 원스톱 서재 등록 파이프라인 구축 (Phase 53)
- **배경**:
  - 기존의 ISBN 직접 입력/스캔 방식에 더해, 제목/저자 키워드 검색으로 여러 권의 후보 도서(표지, 제목, 저자, 출판사, 쪽수, 소개글)를 조회하고 사용자가 원하는 책을 콕 집어 원스톱 등록할 수 있는 직관적 UX 구축.
  - 향후 3단계 데이터 진화(국립도서관 KDC 힌트 ➔ LLM 감성 번역 ➔ StoryGraph식 유저 집단지성 피드백 루프)의 엔진이 될 도서 줄거리 소개글(`description`)과 장르 출처(`genre_source`) 메타데이터를 선제 확보.
- **수행 내용**:
  1. **실측 기반 API 파라미터 및 노이즈 필터링 검증 (Phase 1)**:
     - `YES_24_API_KEY` 인증 통과 (200 OK) 및 Rate Limit(초당 10회, 일일 20,000회) 실측.
     - `detail=Y` 파라미터 적용 시 `pages: 268`(정수 쪽수), `cover`(앞표지), `sideCover`(책등), `contentDetail.bookIntroduction`(소개글)이 1회 호출로 원스톱 확보됨을 확인 (등록 시 재호출 0회 최적화).
     - 묶음 세트 상품의 `isbn13` 빈 문자열(결측) 자동 제외 필터링 및 동일 ISBN In-memory Dedup 규칙 수립.
     - 오타 자동 교정 시 원본 `query` 에코 및 프론트 안내 라벨 UX 확립.
  2. **DB 스키마 선반영 및 ORM/DTO 동기화 (Phase 2)**:
     - Alembic 마이그레이션 `010_add_description_and_genre_source.py`: `core.library_book` 테이블에 `description TEXT NULL`, `genre_source VARCHAR(20) NOT NULL DEFAULT 'KDC'` 추가.
     - `LibraryBook` ORM 모델에 두 컬럼 매핑.
     - Pydantic DTO(`CreateLibraryBookRequest`, `CreateLibraryBookResponse`, `LibraryBookItemResponse`, `LibraryBookDetailResponse`, `UpdateLibraryBookRequest`, `UpdateLibraryBookResponse`, `ExternalBook`, `SearchLibraryBookDetail`, `BookSearchItem`, `BookSearchResponse`) 전수 동기화.
  3. **백엔드 클라이언트 및 검색/등록 파이프라인 구현 (Phase 3)**:
     - `Yes24Client` (`app/services/yes24.py`): 10초 타임아웃, Graceful Fallback, 15분 인메모리 TTL 캐시.
     - `ALLOWED_COVER_HOSTS`에 `image.yes24.com`, `yes24.com` 추가하여 표지 URL 검증 통과 보장.
     - `GET /api/v1/books/search`: `query` 수신 시 YES24 검색 수행, 회원 서재 기등록 여부(`isRegistered`) 실시간 일괄 매핑, 원본 `query` 에코 (`BookSearchResponse`).
     - `BookService.create_book` 및 `update_book`: `description` 및 `genre_source` 영속화 및 반환.
  4. **3-Tier 품질 검증 (Phase 4)**:
     - `tests/test_search.py` (키워드 검색 성공, query 에코, is_registered 매핑, Dedup/필터링/캐시 단위 검증 3건).
     - `tests/test_books.py` (`description`, `genre_source` 등록 및 수정 영속화 검증 1건).
     - Ruff 포맷/린트 100% 무결점 (112개 파일).
     - Mypy 정적 타입 체크 100% 무결점 (102개 소스 파일).
  5. **PR 머지 및 배포 완료**:
     - PR [#40](https://github.com/DPYB/backend-core-api/pull/40) 생성 및 CI/Lint 전수 통과 확인 후 `develop` 브랜치에 정상 머지 완료 (`aa58741`).
- **다음 세션에서 이어 진행할 작업**:
  1. **프론트엔드 검색 UI 연동** (`frontend-reader-web#118` 연동 참조):
     - 검색창(`GET /api/v1/books/search?query=...`) 연동 및 도서 선택 시 `POST /api/v1/library/books` 등록 확인.
  2. **Google Cloud Run 배포 마이그레이션**:
     - `YES_24_API_KEY` 환경변수 주입 및 컨테이너 기동 마이그레이션 검증.


## 2026-10-08: 하네스 문서 슬림화, 롤링 아카이빙 및 Python 자동 검증 체계 구축 (Phase 54)
- **배경**:
  - `HANDOFF.md`가 739줄로 비대화되어 AI 컨텍스트 토큰 낭비 및 관리 부담이 증가함.
  - `backend-ai-agent#59` 및 `frontend-reader-web#121`에서 검증 완료된 DPYB 표준 하네스 규격을 본 레포(`backend-core-api`)에 이식하여 문서 슬림화 및 기계적 검증 자동화 완결.
- **수행 내용**:
  1. **사전 백업 및 아카이빙 (.harness/archive/)**:
     - `.harness/archive/` 생성 및 과거 9월 세션 로그 전체(639줄)를 `.harness/archive/HANDOFF_2026-09.md`로 이동 및 백업.
     - 본문 `HANDOFF.md`를 최근 4개 세션(98줄)으로 슬림화하고 타 레포 침범 방지 정제 (`frontend-reader-web#115`, `frontend-reader-web#118` 참조 처리).
  2. **검증 스크립트 구축 (`scripts/check_harness.py`)**:
     - HANDOFF 라인 수(<=200) 및 세션 수(<=5), STATE 라인 수(<=150), DECISIONS 라인 수(<=150) & 용량(<=20KB), archive 파일명 ISO 표준 규격, 타 레포 격리 5대 규칙 기계적 검증 스크립트 작성 및 실행 권한(`chmod +x`) 부여.
  3. **토큰 보호 설정**:
     - `.agyignore` 및 `.claude/settings.json`에 `.harness/archive/` 차단 설정 생성.
  4. **AGENTS.md 표준 동기화**:
     - DPYB 5대 파일 및 상한 규격 최신화, 본 레포 백엔드 고유 도메인(RDBMS 영속화 SSOT, LexoRank, KDC 체계, 사서 4종 등) 및 계층형 3-Tier 검증 체계 100% 보존.
  5. **품질 검증 통과**:
     - `python3 scripts/check_harness.py` 통과.
     - `uv run ruff format --check .` 및 `uv run ruff check .` 100% 무결점 통과.
     - `uv run mypy .` (103개 소스 파일 통과).
     - `uv run pytest -m "not integration" -x` (132개 테스트 전수 통과, 18.25s).
- **다음 세션에서 이어 진행할 작업**:
  1. **Google Cloud Run 배포 마이그레이션**:
     - Cloud Run 배포 가이드 및 워크플로우 구성, `YES_24_API_KEY` 환경변수 주입 검증.
  2. **데모 계정 자동 청소 크론 최적화**:
     - `.github/workflows/cleanup-demo.yml` 실행 주기 단축 및 게스트 리셋 연동.


## 2026-10-16: 회원가입/인증 엔드포인트 보안 강화 및 Gmail 쿼터 다계층 보호 (Phase 55)
- **배경**:
  - `/signup/resend`의 30초 쿨다운만으로는 이메일 변경 가입을 통한 타인 메일 폭탄(Mail Bombing)과 Gmail 일일 500통 쿼터 고갈을 막을 수 없음.
  - `/signup` 엔드포인트의 Rate Limit 부재, Read-then-Write 동시 요청 레이스 컨디션, `/signup/confirm`의 6자리 난수(90만 개) 브루트포스 대입 취약점, 운영 환경 SMTP 설정 누락 시 Silent Fallback 문제를 원천 차단하기 위해 다계층 보안망 구축.
- **수행 내용**:
  1. **IP 추출 안전성 및 Rate Limit 구축 (`app/core/rate_limit.py`)**:
     - `CF-Connecting-IP` 최우선 신뢰 및 `X-Forwarded-For` 역순 탐색(스푸핑 방어) 안전 IP 파서 구현.
     - `auth_rate_limiter`: `/signup`(분당 5회), `/signup/resend`(분당 3회), `/signup/confirm`(분당 10회) IP Rate Limit 적용.
  2. **DB 기반 24시간 쿼터 상한 & DoS 방어 모니터링 (`app/services/email_service.py`)**:
     - `EmailService.check_email_quota`: 동일 이메일 최근 24시간 5회 초과 시 429 차단, 전체 400통 도달 시 `[QUOTA_ALERT]` 경고 로그(Dry-run) 출력.
  3. **동시성 안전성 및 락/트랜잭션 분리 (`app/routers/auth.py`, `app/services/member_service.py`)**:
     - `/signup/resend`: `Member` 행 `with_for_update()` 락 ➔ 쿨다운/쿼터 검증 ➔ 레코드 commit(락 즉시 해제) ➔ 트랜잭션 밖에서 외부 비동기 SMTP 발송 패턴 적용 (Supabase Pooler 점유 최소화).
     - `/signup`: 동시 가입으로 인한 DB `uq_members_email_active` 충돌 시 `IntegrityError`를 catch하여 반드시 `await db.rollback()` 수행 후 409 `EmailAlreadyExistsException` 안전 반환 (`PendingRollbackError` 원천 방지).
  4. **브루트포스 차단 및 코드 즉시 파기 (`app/models/member.py`, Alembic `011`)**:
     - Alembic 마이그레이션 `011_add_failed_attempts_to_email_verifications.py` 생성 및 `EmailVerification.failed_attempts` 매핑.
     - `/signup/confirm`: `with_for_update()` 락, 불일치 시 `failed_attempts += 1`, 5회 도달 시 `expires_at = now - 1s`로 덮어써서 물리적 만료 처리 (추가 시도 원천 차단, 최대 시도 5코드×5회=25회/90만 통제).
  5. **앱 기동 시점 SMTP Fail-Fast 검증 (`app/config.py`)**:
     - `validate_production_settings()`에서 `ENV in ("production", "staging")`일 때 `SMTP_USER`/`SMTP_PASSWORD` 누락 시 `ValueError` 발생시켜 컨테이너 기동 즉시 fail-fast 보장.
  6. **테스트 및 품질 검증 통과**:
     - `tests/conftest.py`에 `reset_rate_limiters` autouse 픽스처 추가하여 테스트 간 격리 보장.
     - `tests/test_signup.py`에 IP 제한, 이메일별 쿼터, confirm 5회 오답 차단 및 6회차 정답 차단, IntegrityError 롤백 409, SMTP fail-fast 검증 테스트 추가 (10개 테스트 전수 통과).
     - 전체 137개 단위 테스트 100% 통과 (18.36s), ruff 및 mypy 100% 무결점 통과.
- **다음 세션에서 이어 진행할 작업**:
  1. **Google Cloud Run 배포 마이그레이션 & 운영 검증**:
     - Cloud Run 배포 가이드 및 워크플로우 구성, `YES_24_API_KEY` 환경변수 주입 검증.
  2. **프론트엔드 Turnstile(봇 방지 CAPTCHA) 연동**:
     - 가입 폼 Turnstile 검증 서버 siteverify 연동 및 400통 상한 Hard 차단 전환.
  3. **데모 계정 자동 청소 크론 최적화**:
     - `.github/workflows/cleanup-demo.yml` 실행 주기 단축 및 게스트 리셋 연동.

## 2026-10-18: 도서 ISBN-10/13 표준 검증 및 EAN-13 변환 유틸리티 적용 (Phase 56)
- **배경**:
  - 도서 등록/수정 및 검색 시 하이픈/공백 혼용, 10자리(ISBN-10)와 13자리(ISBN-13) 혼용, 결측치/빈 문자열 혼용으로 인해 동일 도서 중복 등록 및 검색 실패 위험 존재.
  - Modulo-11 ISBN-10 검증, EAN-13 가중치 체크디지트 재계산 변환 및 13자리 표준화를 도입하여 서지 데이터 무결성 확보.
- **수행 내용**:
  1. **공통 ISBN 유틸리티 구축 (`app/core/isbn.py`, `app/core/__init__.py`)**:
     - `validate_isbn10`: 10자리 길이, 체크디지트 'X'/'x' 대소문자 허용 및 Modulo-11 가중치 합 검증.
     - `calculate_isbn13_check_digit`: 12자리 숫자에 1, 3 교대 가중치 적용하여 13번째 체크디지트 산출.
     - `convert_isbn10_to_isbn13`: 유효한 ISBN-10 확인 후 `978` + 앞 9자리 + 신규 체크디지트 결합.
     - `validate_isbn13`: 13자리 길이 및 EAN-13 체크디지트 유효성 검증.
     - `normalize_isbn`: 하이픈/공백 제거 및 10자리 유효 시 13자리 자동 변환 승격, 빈 문자열 `None` 처리.
     - `normalize_and_validate_isbn`: VALID_13, CONVERTED_10, INVALID, MISSING 4대 상태 엄격 판정.
  2. **요청 DTO 유효성 검사 적용 (`app/schemas/library_book.py`)**:
     - `CreateLibraryBookRequest`, `UpdateLibraryBookRequest`에 `@field_validator("isbn", mode="before")` 적용.
     - 공백/하이픈 제거, 10자리 ➔ 13자리 자동 변환, 빈 문자열/공백은 `None` 처리, 유효하지 않은 ISBN은 422 에러 거부.
  3. **검색 API ISBN 정규화 (`app/routers/search.py`)**:
     - 검색어 파싱 시 마지막 자리 'X'/'x' 지원 및 10자리 입력 시 13자리로 정규화하여 YES24/도서관 검색 연동.
  4. **도서 서비스 영속화 안전성 보장 (`app/services/book_service.py`)**:
     - 도서 등록/수정 시 공백 문자열 DB `NULL` 저장 보장 및 ISBN-10/13 중복 등록 차단.
  5. **테스트 및 품질 검증 통과**:
     - `tests/test_isbn.py` 14종 신규 단위/통합 테스트 작성 (383줄).
     - 기존 테스트 더미 ISBN 픽스처 표준 유효 번호로 정비.
     - 전체 151개 단위 테스트 100% 통과 (18.20s), Ruff 및 Mypy 100% 무결점 통과.
- **다음 세션에서 이어 진행할 작업**:
  1. **Phase 56 PR 생성 및 develop 머지 지원**:
     - PR 생성 및 CI 통과 후 develop 머지 지원.
  2. **Phase 54: YES24 단건 조회 + AI Agent 장르 분류 연동**:
     - Alembic 012 `genre_confidence` 추가 및 `POST /api/v1/classify-genre` 연동.


## 2026-10-18: YES24 단건 조회 + AI Agent 장르 분류 연동 및 캐시 재사용 파이프라인 구축 (Phase 57)
- **배경**:
  - AI 에이전트 서비스(`backend-ai-agent#68`)의 Gemini Flash-Lite 기반 `POST /api/v1/classify-genre` API 구축 완료에 맞춰, 본 레포(`backend-core-api`)의 도서 등록 및 서지 융합 파이프라인 연동.
  - YES24(소개글/쪽수/표지) + 국립중앙도서관(KDC 힌트) + AI 장르 분류 클라이언트(장르/세부주제 정밀 판정) 삼각 결합 완성.
  - 동일 ISBN 재등록 시 캐시 재활용으로 LLM 호출 최소화 및 개인 수정값 전파 방지(`genre_source != 'USER'`).
- **수행 내용**:
  1. **Alembic 마이그레이션 및 ORM/DTO 갱신 (`alembic/versions/012_add_genre_confidence.py`)**:
     - `core.library_book` 테이블에 `genre_confidence FLOAT NULL` 컬럼 추가.
     - `LibraryBook` ORM 모델 및 Pydantic DTO(`CreateLibraryBookRequest`, `LibraryBookItemResponse`, `LibraryBookDetailResponse`, `UpdateLibraryBookRequest`, `UpdateLibraryBookResponse`, `ExternalBook`, `SearchLibraryBookDetail`, `BookSearchItem`) 동기화.
  2. **YES24 단건 조회 및 상품 링크 지원 (`app/services/yes24.py`)**:
     - `lookup_by_isbn(isbn: str)` 단건 조회 및 15분 TTL 캐싱 구축, 상품 상세 URL(`link`) 파싱 지원.
     - 불일치 ISBN 첫 번째 결과 채택 안티패턴 제거 및 정규화 기반 엄격한 ISBN 일치 검사 구축.
  3. **AiAgentClient 신설 및 Graceful Fallback (`app/services/ai_agent.py`)**:
     - `classify_genre` 비동기 클라이언트 구현 (`POST /api/v1/classify-genre`).
     - 2.5초 하드 타임아웃(`httpx.Timeout(2.5)`) 및 외부 에러/지연 시 KDC 기반 `parse_to_genre_and_subject` Graceful Fallback (`source="KDC_FALLBACK"`).
  4. **도서 등록 캐시 재사용, 일관성 보장 및 사용자 수정 보호 (`app/services/book_service.py`)**:
     - `create_book`: 동일 ISBN 기등록 도서 탐색 시 `genre_source != 'USER'`인 경우 기존 장르/주제/신뢰도 재사용 (LLM 호출 $0 최적화).
     - LLM 캐시 히트 시 장르/출처/신뢰도 일관성 보장(기존 요청 KDC 장르가 있더라도 LLM 캐시 장르로 승격) 및 `genre_source` 4대 허용값(`ALLOWED_GENRE_SOURCES`) 검증.
     - 사용자 수동 입력/수정(`genre_source == 'USER'`)은 AI 분류 결과로 덮어쓰지 않고 최우선 보존.
  5. **서지 검색 병렬 융합 (`app/routers/search.py`)**:
     - `_search_by_isbn`: `asyncio.gather`로 YES24와 국립중앙도서관 동시 조회 후 메타데이터 우선순위 합성 (편측 실패 격리).
  6. **3-Tier 품질 검증 통과**:
     - `tests/test_ai_agent.py` (6종), `tests/test_genre_pipeline.py` (11종) 단위/통합 테스트 신설.
     - 168개 단위 테스트 전수 통과 (19.23s), Ruff 포맷/린트 및 Mypy 정적 타입 체크 100% 무결점.
- **다음 세션에서 이어 진행할 작업**:
  1. **Phase 57 PR 생성 및 develop 머지 지원**:
     - 로컬 커밋 상태 점검 후 PR 생성 및 CI 통과 확인.
  2. **Google Cloud Run 배포 마이그레이션**:
     - `YES_24_API_KEY` 실환경 환경변수 주입 및 컨테이너 기동 검증.
