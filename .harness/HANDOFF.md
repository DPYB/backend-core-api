# HANDOFF (세션별 서술 로그, append-only)

## 2026-10-20: Cloudflare R2 도서 커스텀 표지(frontcover) Presigned URL 파이프라인 및 무결성 검증 구축 (Phase 60)
- **배경**:
  - 도서 직접 등록(독립 출판물, 절판 도서, 표지 부재 도서, 실물 책 직접 촬영) 및 개인화 커스텀 표지 업로드를 위해 Cloudflare R2 버킷(`dpyb-public`) 다이렉트 Presigned PUT URL 파이프라인 구축.
  - 가짜/타인 객체 키 도용, 미업로드 객체 등록, 5MB 용량 초과, 비이미지 위조 파일 등록을 원천 차단하고 표지 변경 및 도서 삭제 시 미사용 R2 이미지 안전 정리(Clean-up) 구현.
- **수행 내용**:
  1. **DTO 정의 (`app/schemas/library_book.py`)**:
     - `BookCoverPresignedUrlRequest` (`contentType: str = "image/webp"`).
     - `BookCoverPresignedUrlResponse`: `status="success"`, `data: {uploadUrl, publicUrl, key}` 및 기존 DTO 듀얼 필드(`presignedUrl`, `imageUrl`, `expiresIn=600`) 직렬화 지원.
  2. **범용 스토리지 서비스 확장 (`app/services/storage_service.py`)**:
     - `generate_book_cover_presigned_url`: `frontcover/{env}/{uuid}.{ext}` 키 발급 및 서명 쿼리스트링 로깅 마스킹.
     - `verify_uploaded_book_cover`: R2 CDN URL에 대해 frontcover 경로, R2 실제 객체 존재 여부(`head_object`), 5MB 상한, Content-Type, 16바이트 매직 넘버 검증 및 위조 파일 자동 삭제.
     - `delete_image_if_exists`: 프로필/스크랩/도서 커스텀 표지 공용 미사용 객체 안전 삭제 연동.
  3. **공인 표지 호스트 등록 및 도서 서비스 연동 (`app/services/national_library.py`, `app/routers/books.py`, `app/services/book_service.py`)**:
     - `ALLOWED_COVER_HOSTS`에 R2 CDN 도메인(`cdn.ai0208.xyz`) 등록.
     - `POST /api/v1/library/books/cover/presigned-url` 엔드포인트 신설 (게스트/데모 403 차단).
     - `create_book`: 커스텀 R2 표지 무결성 검증 후 DB 저장.
     - `update_book`: 신규 표지 검증 및 DB 커밋 성공 후 이전 커스텀 표지 자동 삭제.
     - `delete_book`: 도서 삭제 시 소속된 커스텀 표지 안전 정리.
  4. **3-Tier 품질 검증 통과**:
     - `tests/test_storage.py`에 도서 표지 Presigned URL, 무결성 검증, 위조 차단, 도서 라이프사이클 14종 신규 테스트 작성 (총 53종 전수 통과).
     - 전체 231개 단위 테스트 100% 그린 (20.22s), Ruff 포맷/린트 및 Mypy 정적 타입 체크 100% 무결점.
- **다음 세션에서 이어 진행할 작업**:
  1. **3대 이미지(프로필, 스크랩, 도서 표지) Presigned URL 연동 모니터링**:
     - 실환경 R2 업로드 동작 모니터링 및 API 인터페이스 규격 지원.
  2. **상용화 대비 보안 및 운영 체계 점검**:
     - 보안 응답 헤더 미들웨어 및 환경설정 점검.

## 2026-10-20: Cloudflare R2 문장 수집(Scrap) 이미지 Presigned URL 파이프라인 및 무결성 검증 구축 (Phase 59)
- **배경**:
  - 문장 수집 스크랩 시 이미지 바이너리가 백엔드 메모리/대역폭을 거치지 않도록 Cloudflare R2 버킷(`dpyb-public`) 다이렉트 Presigned PUT URL 파이프라인 구축.
  - 가짜/타인 객체 키 도용, 미업로드 객체 등록, 5MB 용량 초과, 비이미지 위조 파일 등록을 원천 차단하고 스크랩 수정/삭제 시 미사용 R2 이미지 안전 정리(Clean-up) 구현.
- **수행 내용**:
  1. **DTO 정의 (`app/schemas/scrap.py`)**:
     - `ScrapImagePresignedUrlRequest` (`contentType: str = "image/webp"`), `ScrapImagePresignedUrlResponse` (`presignedUrl`, `imageUrl`, `expiresIn=600`).
  2. **범용 스토리지 서비스 확장 (`app/services/storage_service.py`)**:
     - `generate_scrap_image_presigned_url`: `quote/{env}/{member_id}_{timestamp}_{uuid8}.{ext}` 키 발급 및 서명 파라미터 로깅 마스킹.
     - `verify_uploaded_scrap_image`: R2 CDN URL에 대해 소유권(`member_id_`), R2 실제 객체(`head_object`), 5MB 상한, MIME 타입, 16바이트 매직 바이트 검증 및 위조 객체 자동 삭제(`_safe_delete_object`).
     - Base64 Data URL 및 외부 이미지 URL에 대한 100% 하위 호환성 보장.
     - `delete_image_if_exists`: 프로필/스크랩 공용 미사용 객체 안전 삭제 연동.
  3. **엔드포인트 신설 및 비즈니스 로직 연동 (`app/routers/scraps.py`, `app/services/scrap_service.py`)**:
     - `POST /api/v1/library/scraps/presigned-url` 엔드포인트 신설 (게스트/데모 403 차단 가드).
     - `create_scrap`: R2 CDN URL 검증 후 DB 영속화.
     - `update_scrap`: 신규 이미지 검증 및 DB 커밋 완료 후 이전 이미지 R2 정리.
     - `delete_scrap`: 스크랩 삭제 시 소속된 R2 이미지 안전 정리.
  4. **3-Tier 품질 검증 통과**:
     - `tests/test_storage.py`에 스크랩 Presigned URL, 무결성 검증, 위조 차단, E2E 라이프사이클 테스트 16종 신설 (총 39종 전수 통과).
     - 전체 217개 단위 테스트 100% 그린 (22.12s), Ruff 포맷/린트 및 Mypy 정적 타입 체크 100% 무결점.
- **다음 세션에서 이어 진행할 작업**:
  1. **Phase 59 PR 생성 및 develop 머지 지원**:
     - 로컬 커밋 및 PR 생성, CI 통과 확인.
  2. **Google Cloud Run 배포 마이그레이션 & 운영 검증**:
     - Cloud Run 배포 가이드 및 워크플로우 구성, `YES_24_API_KEY` 환경변수 주입 검증.

## 2026-10-19: Cloudflare R2 Presigned URL 다이렉트 업로드 파이프라인 구축 & 프로필 사진 연동 (Phase 58)
- **배경**:
  - 사용자 프로필 사진 업로드 시 백엔드 서버 부하(대역폭 및 CPU/RAM)를 $0로 차단하기 위해 Cloudflare R2 버킷(`dpyb-public`) 다이렉트 Presigned PUT URL 파이프라인 구축.
  - 가짜/타인 객체 키 등록, 미업로드 객체 등록, 용량 초과 등 스토리지 무결성 침해를 원천 방어하고 이전 커스텀 이미지 자동 정리(Clean-up) 구현.
- **수행 내용**:
  1. **의존성 및 환경설정 구축 (`pyproject.toml`, `requirements.txt`, `app/config.py`, `.env.example`)**:
     - `boto3>=1.34.0` 의존성 추가 및 `requirements.txt` 도커 빌드 파일 동기화 완료 (PR #45, #46).
     - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`("dpyb-public"), `R2_PUBLIC_URL_PREFIX`("https://cdn.ai0208.xyz"), `R2_ENV_PREFIX`("beta") 환경변수 구성.
  2. **범용 스토리지 서비스 구현 (`app/services/storage_service.py`)**:
     - `StorageService`: boto3 S3 클라이언트 팩토리, 4대 MIME 타입(WebP, PNG, JPEG, GIF) 매핑 및 5MB 상한 검증.
     - 고유 객체 키 생성 규칙: `{category}/{env}/{member_id}_{timestamp}_{uuid8}.{ext}`.
     - 600초 유효기간 Presigned PUT URL 생성 및 로그 시 서명 쿼리스트링 마스킹.
     - `verify_uploaded_profile_image`: R2 CDN URL에 대해 본인 키 소유권 및 실제 객체 존재 여부(`head_object`), 16바이트 매직 넘버 검사 및 불량 객체 자동 삭제.
     - `delete_image_if_exists`: DB 커밋 완료 후 이전 커스텀 이미지 안전 삭제 연동.
  3. **DTO 및 엔드포인트 신설 (`app/schemas/member.py`, `app/routers/users.py`, `app/services/member_service.py`)**:
     - `ProfileImagePresignedUrlRequest`, `ProfileImagePresignedUrlResponse` Pydantic DTO 추가.
     - `POST /api/v1/users/me/profile-image/presigned-url` 및 별칭 엔드포인트 신설 (게스트/데모 계정 차단).
     - `PATCH /api/v1/users/me`: `MemberService.update_profile` 내 무결성 검증 및 이전 이미지 정리 통합.
  4. **3-Tier 품질 검증 통과**:
     - `tests/test_storage.py` 신설: Mock S3 기반 단위 테스트, 키/MIME 매핑, 인증/인가/용량초과/미존재 가드, E2E 갱신 23종 전수 통과.
     - 전체 201개 단위 테스트 100% 그린 (21.73s), Ruff 포맷/린트 및 Mypy 타입 체크 무결점.
- **다음 세션에서 이어 진행할 작업**:
  1. **Phase 59: 문장 수집(Scrap) 이미지 Presigned URL 파이프라인 및 무결성 검증 구축**:
     - `POST /api/v1/library/scraps/presigned-url` 엔드포인트 신설 (`ScrapImagePresignedUrlRequest/Response` DTO)
     - `StorageService.generate_scrap_image_presigned_url`: `quote/beta/{member_id}_{timestamp}_{uuid}.{ext}` Presigned PUT URL 발급
     - `StorageService.verify_uploaded_scrap_image`: 소유권, R2 객체 존재 여부, 5MB 상한, 16바이트 매직 넘버 검증 및 위조 파일 자동 삭제
     - `create_scrap` & `update_scrap` 연동 및 DB 커밋 후 이전 이미지 정리
     - 단위/통합 테스트 작성 (201개 단위 테스트 100% 그린 유지) 및 PR 생성
  2. **Cloud Run 배포 및 R2 실환경 모니터링**:
     - PR #46 머지 후 Cloud Run 자동 빌드 배포 성공 확인 및 프론트엔드 연동 지원.

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
