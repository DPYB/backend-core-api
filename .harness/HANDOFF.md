# HANDOFF (세션별 서술 로그, append-only)

## 2026-10-19: Cloudflare R2 Presigned URL 다이렉트 업로드 파이프라인 구축 & 프로필 사진 연동 (Phase 58)
- **배경**:
  - 사용자 프로필 사진 업로드 시 백엔드 서버 부하(대역폭 및 CPU/RAM)를 $0로 차단하기 위해 Cloudflare R2 버킷(`dpyb-public`) 다이렉트 Presigned PUT URL 파이프라인 구축.
  - 가짜/타인 객체 키 등록, 미업로드 객체 등록, 용량 초과 등 스토리지 무결성 침해를 원천 방어하고 이전 커스텀 이미지 자동 정리(Clean-up) 구현.
- **수행 내용**:
  1. **의존성 및 환경설정 구축 (`pyproject.toml`, `app/config.py`, `.env.example`)**:
     - `boto3>=1.34.0` 의존성 추가.
     - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`("dpyb-public"), `R2_PUBLIC_URL_PREFIX`("https://cdn.ai0208.xyz"), `R2_ENV_PREFIX`("beta") 환경변수 구성.
  2. **범용 스토리지 서비스 구현 (`app/services/storage_service.py`)**:
     - `StorageService`: boto3 S3 클라이언트 팩토리, 4대 MIME 타입(WebP, PNG, JPEG, GIF) 매핑 및 5MB 상한 검증.
     - 고유 객체 키 생성 규칙: `{category}/{env}/{member_id}_{timestamp}_{uuid8}.{ext}`.
     - 600초 유효기간 Presigned PUT URL 생성 및 로그 시 서명 쿼리스트링 마스킹.
     - `verify_uploaded_profile_image`: R2 CDN URL에 대해 본인 키 소유권 및 실제 객체 존재 여부(`head_object`), 용량/타입 검증.
     - `delete_image_if_exists`: 프로필 변경 시 이전 커스텀 이미지 삭제 연동.
  3. **DTO 및 엔드포인트 신설 (`app/schemas/member.py`, `app/routers/users.py`, `app/services/member_service.py`)**:
     - `ProfileImagePresignedUrlRequest`, `ProfileImagePresignedUrlResponse` Pydantic DTO 추가.
     - `POST /api/v1/users/me/profile-image/presigned-url` 및 별칭 엔드포인트 신설 (게스트/데모 계정 차단).
     - `PATCH /api/v1/users/me`: `MemberService.update_profile` 내 무결성 검증 및 이전 이미지 정리 통합.
  4. **3-Tier 품질 검증 통과**:
     - `tests/test_storage.py` 신설: Mock S3 기반 단위 테스트, 키/MIME 매핑, 인증/인가/용량초과/미존재 가드, E2E 갱신 20종 전수 통과.
     - 전체 198개 단위 테스트 100% 그린 (18.71s), Ruff 포맷/린트 및 Mypy 타입 체크 무결점.
- **다음 세션에서 이어 진행할 작업**:
  1. **Phase 58 PR 생성 및 develop 머지 지원**:
     - 로컬 커밋 상태 점검 후 PR 생성 및 CI 통과 확인.
  2. **향후 문장 수집 스크랩(Scrap) 원본 이미지 연동**:
     - `StorageService`의 `category="scrap"`을 활용한 스크랩 Presigned URL 엔드포인트 확장.

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
