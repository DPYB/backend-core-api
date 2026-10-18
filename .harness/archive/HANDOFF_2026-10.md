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
