# HANDOFF (세션별 서술 로그, append-only)

## 2026-10-25: 자격증명 보안 강화 (Refresh Token Response Body 노출 제거 및 HttpOnly 쿠키 단일화) (Phase 65)
- **배경**:
  - `POST /api/v1/auth/login`, `/social/google`, `/social/kakao`, `/refresh`, `/guest` 응답 JSON Body에 평문 `refreshToken`이 노출되어 XSS 공격 표면이 존재하던 취약점 해소.
  - 프론트엔드 전수 조사 결과 Body 토큰 사용처 0건(HttpOnly 쿠키 전용 갱신 완비) 확인에 따라, 응답 스키마 및 직렬화에서 해당 필드를 완전히 배제(null이 아닌 필드 제거).
- **수행 내용**:
  1. **응답 DTO 스키마 정제 (`app/schemas/auth.py`)**:
     - `TokenResponse`: `refresh_token` 필드 및 `@computed_field refresh_token_snake` 완전 제거.
     - `GuestLoginResponse`: `refresh_token: str | None` 필드 및 `refresh_token_snake` 완전 제거.
     - `access_token` 및 `@computed_field access_token_snake`는 API 계약 호환성을 위해 100% 정상 유지.
  2. **라우터 응답 생성부 정제 (`app/routers/auth.py`)**:
     - `dev_login`, `google_social_login`, `kakao_social_login`, `refresh_token`, `issue_guest_token`에서 `refresh_token` 매개변수 제거.
     - `_set_refresh_cookie` 쿠키 발급 및 `POST /auth/logout` 쿠키 만료/삭제(`Max-Age=0`) 로직 100% 온전히 보존.
  3. **3-Tier 품질 검증 통과**:
     - `tests/test_auth_credential_security.py` 7종 신규 보안 회귀 테스트 작성 (Body 필드 부재, Access Token 유지, 쿠키 발급/갱신/만료, 예외 응답 비노출 등 전수 통과).
     - 기존 `tests/test_social_auth_and_members.py` 갱신 통과.
     - 306개 전체 단위 테스트 100% 그린 (27.23s), Ruff 포맷/린트 및 Mypy 126개 소스 파일 100% 무결점 통과.
- **다음 세션에서 이어 진행할 작업**:
  1. **Phase 65 커밋 및 PR 생성 (사용자 컨펌 후 진행)**:
     - `feat/auth-credential-security` 브랜치 커밋 및 PR 생성.
  2. **Phase 65-2 로그 노출 점검 또는 Phase 66 Google Books categories 직렬화 착수**:
     - 사용자 피드백에 맞춰 후속 과제 진행.

## 2026-10-25: 베타 테스터 가입 버튼 비활성화 및 로그아웃 세션 이슈 분석/해결 지원
- **배경**:
  - 베타 테스터들의 "회원가입 버튼 비활성화(🚫)" 및 "로그아웃 시 즉시 로그인창으로 안 가고 새로고침해야 풀리며 /refresh 401 발생" 이슈 원인 분석 및 해결.
- **수행 내용**:
  1. **회원가입 버튼 비활성화 원인 분석 및 해결 지원**:
     - 원인: 프론트엔드 비밀번호 복잡도 정규식(`PW_RE`)이 영문 대문자(`A-Z`)를 필수로 요구함에도 플레이스홀더에 누락되고 에러 문구가 없어 사용자가 소문자만 입력 시 버튼이 잠기는 결함 규명.
     - 프론트엔드 PR #196 (`feat[signup]: 비밀번호 유효성 검사 실시간 피드백 및 플레이스홀더 명확화`) 검증 및 머지 지원 완료.
  2. **로그아웃 세션 잔류 및 /refresh 401 오류 해결 지원**:
     - 원인: 백엔드 `POST /api/v1/auth/logout` 쿠키 삭제 후 프론트엔드가 메모리 상태를 동기 리셋하지 않고 단순 내부 라우팅을 수행하여 3D/Context 잔류, 새로고침 시 이미 지워진 쿠키로 `/refresh`를 찔러 401이 발생한 메커니즘 규명.
     - 프론트엔드 PR #197 (`fix[auth]: 로그아웃 시 클라이언트 상태 무조건 초기화 및 로그인 페이지 클린 리로드`) 검증 및 머지 지원 완료.
  3. **인프라 및 모니터링 정책 정리**:
     - Render 서비스는 완전 배제 확정 및 Google Cloud Run 단일 배포 환경으로 일원화.
     - 향후 Cloud Run 4xx/5xx 로그에 대한 Discord 실시간 웹훅 모니터링 아키텍처 방안 수립.
- **다음 세션에서 이어 진행할 작업**:
  1. **Phase 65 자격증명 보안 강화 (Refresh Token Body 노출 제거 & 쿠키 단일화)**:
     - DTO 정제, 쿠키 수명주기 검증 및 단위/통합 테스트 진행.
  2. **Cloud Run 로그 모니터링 체계 심화 구축**:
     - Discord Webhook 알림 파이프라인 심도 있는 설계 및 구축.

## 2026-10-24: 도서 분류 체계(KDC/DDC/Genre) 물리적 모듈 분리 및 삼각 데이터 계약 정비 (Phase 64)
- **배경**:
  - `kdc_mapper.py` 내 DDC 매핑 공존으로 인한 네이밍/책임 불일치(Misnomer) 해소 및 분류 체계별 물리적 모듈 격리.
  - `catalog`(KR vs US), `data_source`(YES24, GOOGLE, NL), `genre_source`(KDC, DDC, LLM, FALLBACK, USER) 삼각 데이터 계약 확립.
  - KDC 004/005 컴퓨터과학 도서의 안 A(대분류 `GENERAL` + `subject="컴퓨터/IT"` + `displayGenre="컴퓨터/IT"`) 확정 및 사용자 수정값 영구 보호.
- **수행 내용**:
  1. **물리적 모듈 3단 분리 (`app/core/kdc_mapper.py`, `app/core/ddc_mapper.py`, `app/core/genre_mapper.py`)**:
     - `kdc_mapper.py`: 순수 KDC(한국십진분류법 제6판) 전담 매퍼 (`kdc_to_genre`, `kdc_to_subject`, `extract_kdc_code`).
     - `ddc_mapper.py`: 순수 DDC(듀이십진분류법 제23판) 전담 매퍼 신설 (`ddc_to_genre`, `extract_ddc_code`, 400 언어/500 자연과학/600 기술과학/700 예술).
     - `genre_mapper.py`: 통합 장르 오케스트레이터 신설 (`parse_to_genre_and_subject`, `fallback_genre_by_keywords`, `GENRE_KOREAN_NAMES`).
     - PEP 562 `__getattr__` 기반 지연 평가로 순환 참조 방지 및 레거시 import 하위 호환성 100% 보장.
  2. **서지 데이터 계약 및 DTO 정합성 확보**:
     - `data_source`와 `genre_source` 독립성 보장.
     - `ExternalBook` 및 `LibraryBook` DTO에서 `genreName`은 대분류 고유 한글명, `displayGenre`는 세부 주제어 1순위 노출 확립.
     - `update_book` 시 장르/주제어 변경 시 `genre_source="USER"` 승격 및 이후 모든 자동 갱신 덮어쓰기 영구 차단.
  3. **3-Tier 품질 검증 통과**:
     - `tests/test_genre_contract.py` 8대 계약 테스트(T1~T8) 작성 및 전수 통과.
     - `tests/test_ddc_mapper.py`, `tests/test_genre_mapper.py`, `tests/test_kdc_mapper.py` 전수 통과.
     - 299개 전체 단위 테스트 100% 통과 (30.86s), Ruff 및 Mypy 125개 소스 파일 100% 무결점 통과.
- **다음 세션에서 이어 진행할 작업**:
  1. **Phase 64 커밋 및 develop PR 생성**:
     - 사용자 컨펌 후 Phase 63/64 원자적 분할 커밋 및 PR 생성.
  2. **크로스 서비스 데이터 계약 연계 지원**:
     - AI 에이전트 서비스: `CLASSIFY_GENRE_SYSTEM_PROMPT` KDC/DDC 분리 명시 및 `subject` 필수 도출 규칙 반영.
     - 프론트엔드 웹: 장르 칩 표시 순서(`displayGenre || subject || genreLabel(genre)`) 통일.

## 2026-10-24: 해외 도서 베타 연동 최종 게이트 교차 검증 및 프론트엔드 E2E 통과 (Phase 70-6)
- **배경**:
  - 해외 도서(Google Books API) 검색 및 AI 에이전트 서비스 연계 규격에 대한 최종 교차 코드 검증 수행.
  - Track A(유효 ISBN) vs Track B(ISBN 결측) 범위 분리, 서지 검증 생략 여부, `dataSource` 직렬화 및 장르 매핑 무결성 확정.
- **수행 내용**:
  1. **Phase A (읽기 전용 교차 코드 리뷰)**:
     - 코어 서버 동결 유지: `BookSearchItem.isbn: str` 필수 계약 및 `_parse_volume`의 ISBN 결측 도서 Drop 일관성 확인.
     - 에이전트 연동 계약 확인: `dataSource: "GOOGLE"` 파싱, 서지 검증 통과 시에만 조기 반환(`is_valid == True`), Google Books `categories` 미제공에 따른 제목/설명 영문 키워드 매핑 안전망 확인.
  2. **Phase B (최소 보정)**:
     - 코어 서버 코드 변경 0건 (완전 동결) 및 에이전트 연계 계약 보존.
  3. **Phase C & D (3-Tier 검증 및 최종 게이트 판정)**:
     - 본 레포 281개 단위 테스트 100% 그린(23.18s), Ruff/Mypy/Harness 무결점 통과.
     - 최종 판정: `PASS WITH CONDITIONS` (유효 ISBN 도서 기준 프론트엔드 연동 진행 가능).
  4. **프론트엔드 E2E 실환경 상호작용 검증**:
     - 사서 추천 요청 $\to$ SSE 실시간 스트리밍 카드 수신 $\to$ [내 서재 등록] 클릭 $\to$ 회원 서재 영속화 E2E 파이프라인 실환경 정상 작동 최종 확인.
     - Cloud Run에 `GOOGLE_BOOKS_API_KEY` 부재 시에도 500 에러 없이 국립도서관 데이터로 안전 폴백(Graceful Fallback)되는 무중단 안전망 실증.
- **다음 세션에서 이어 진행할 작업**:
  1. **Google Cloud Run 환경변수 등록**:
     - Cloud Run 콘솔에 `GOOGLE_BOOKS_API_KEY` 환경변수 주입 후 라이브 원서 표지/메타데이터 연동 점검.
  2. **Google Books 원본 categories 직렬화 후속 과제 (Phase 63 2단계)**:
     - Core API `BookSearchItem.subject`로 `categories` 매핑 및 AI 서비스 1순위 매핑 활성화 지원.

## 2026-10-23: 책장 선반(Shelf Placement) 배치 일괄 동기화 API 구축 (Phase 62)
- **배경**:
  - 프론트엔드가 3D 책장의 단/층(0, 1, 2단...) 드래그 앤 드롭 배치를 브라우저 `localStorage`로만 임시 관리하고 있어, 새로고침이나 기기 변경 시 배치가 도서 등록순으로 원상 복구되는 한계 해소.
  - 책장 내 단/선반(`shelf_tier`) 및 선반 내 순서(`shelf_order`)를 DB(`core.library_book`)에 영속화하고, 드래그 앤 드롭 완료 시 일괄 동기화하는 API 구축.
- **수행 내용**:
  1. **DB 마이그레이션 (`alembic/versions/013_add_shelf_placement_columns.py`)**:
     - `core.library_book` 테이블에 `shelf_tier INT NOT NULL DEFAULT 0`, `shelf_order INT NOT NULL DEFAULT 0` 컬럼 추가.
     - `(member_id, shelf_tier, shelf_order)` 복합 인덱스(`ix_library_book_member_shelf_placement`) 추가.
  2. **ORM 엔티티 및 DTO 스키마 확장 (`app/models/library_book.py`, `app/schemas/library_book.py`)**:
     - `LibraryBook` 모델에 `shelf_tier`, `shelf_order` 매핑.
     - 도서 4대 응답 DTO(`LibraryBookItemResponse`, `LibraryBookDetailResponse`, `CreateLibraryBookResponse`, `UpdateLibraryBookResponse`)에 `shelfTier`, `shelfOrder` 필드 전면 노출.
     - 일괄 업데이트 요청/응답 DTO(`ShelfPlacementsUpdateRequest`, `ShelfPlacementsResponse`) 정의 및 정수/문자열 키 및 ID 유연한 자동 정규화(Coercion) 검증.
  3. **비즈니스 로직 및 엔드포인트 신설 (`app/services/book_service.py`, `app/routers/books.py`, `app/main.py`)**:
     - `PUT /api/v1/library/books/shelf-placements` 엔드포인트 신설.
     - 단일 격리 트랜잭션 내에서 요청된 모든 도서의 회원 소유권(`member_id == current_user`) 검증, 타인 도서 포함 시 403 차단, 중복 도서 ID 요청 시 400 차단.
     - 도서 등록/수정 시 `shelf_tier`, `shelf_order` 매핑 및 목록 조회(`get_books`) 시 `sortBy=SHELF_PLACEMENT` 정렬(tier -> order -> rank) 옵션 지원.
     - 데모 계정(`demo_allowed_write_routes`) 및 게스트 계정(`guest_allowed_write_routes`) 쓰기 허용 목록에 등록.
  4. **3-Tier 품질 검증 통과**:
     - `tests/test_shelf_placements.py` 10종 신규 단위/통합 테스트 작성 (전수 통과):
       - 0/1/2단 일괄 배치 갱신 및 목록/단건/등록/수정 조회 시 shelfTier/shelfOrder 반환 검증
       - `sortBy=SHELF_PLACEMENT` ASC/DESC 정렬 검증
       - 정수/문자열 키 및 ID 혼합 입력 정규화 검증
       - 빈 assignments, 중복 도서 ID(400), 미존재 도서(404), 타인 도서(403), 비정수 키(400) 방어 검증
       - 데모 계정 쓰기 허용 통과 검증
     - 전체 281개 단위 테스트 100% 그린 (31.60s), Ruff 포맷/린트 및 Mypy 타입 체크 100% 무결점.
- **다음 세션에서 이어 진행할 작업**:
  1. **Phase 62 PR 생성 및 develop 머지 지원**:
     - `feat/shelf-placements` 브랜치 PR 생성 및 리뷰 포인트 확인.
  2. **글로벌 도서 API 연동 (Google Books API - Phase 63 마무리 및 PR)**:
     - 대기 중인 Google Books 연동 로직 검증 및 머지.
