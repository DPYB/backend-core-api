# DECISIONS (결정 히스토리, 최신 결정이 최상단)

결정 내용과 이유만 기록한다. 진행 상황은 `STATE.md`를 본다.

| 날짜 | 결정 | 이유 / 대안 비교 |
| :--- | :--- | :--- |
| 2026-09-16 | 타 서비스(`frontend-reader-web`, `backend-ai-agent`) 통신 계약 일치화 및 소셜 로그인 프로필 통합 반환 | 프론트엔드가 페이징 응답에서 `books` 및 `scraps` 필드를 기대하고(`res.books`, `res.scraps`), AI 에이전트는 `items` 필드를 참조하는 상이점을 해소하기 위해 `LibraryBookPageResponse` 및 `ScrapPageResponse`에 `@computed_field` 듀얼 직렬화를 도입. AI 에이전트 도구 호출 호환을 위해 도서 단건 조회 별칭(`GET /api/v1/books/{book_id}`)과 도서 검색(`GET /api/v1/books/search`)의 ISBN/키워드 통합 검색 및 선택적 인증(`get_optional_member_id`)을 지원. 소셜 로그인(`/social/google`, `/social/kakao`) 응답을 `LoginResponse`로 격상하여 프론트엔드 `AuthProvider`가 별도 조회 없이 사용자 및 사서 프로필을 즉시 동기화하도록 최적화 |
| 2026-09-15 | 동물 사서 4종 페르소나 및 기본 표시명 동기화 (`SEA_SLUG` ➔ '누디') 및 회원 프로필/사서 카탈로그 메타데이터 통합 | AI 에이전트 서비스(`backend-ai-agent`)와의 사서 페르소나 및 프론트엔드 연동 일치를 위해 `SEA_SLUG`의 기본 표시명을 기존 '바다달팽이'에서 '누디'로 개편(`DEFAULT_LIBRARIAN_NAMES`). 사서 마스터 카탈로그(`GET /api/v1/librarian-types`) 및 회원 프로필(`GET /api/v1/users/me`, `GET /api/v1/members/me`)에서 `default_name`, `species`, `mbti`, `genres`, `description`, `ending_style` 메타데이터를 통합 제공하여 프론트엔드의 하드코딩을 제거하고, 사서 획득 시 이름 생략 시 기본 표시명 자동 폴백 적용 |
| 2026-09-15 | 사서 월간 독서 리포트 통계 집계(`GET /api/v1/reports/monthly-stats`) 및 초경량 스톱워치 독서 세션(`record.reading_sessions`) 모델 도입, 도서 '중단' 상태 배제 | 불필요한 '중단' 상태(STOPPED/PAUSED)를 신설하지 않고 기존 3단계(`PLANNED`, `READING`, `COMPLETED`) 체제를 유지하여 '완독/읽는 중 도서'로 간결화. 복잡한 실시간 소켓 대신 프론트엔드 로컬 스톱워치 종료 시 `POST /api/v1/reading-sessions` 호출 단 1회로 독서시간, 페이지 증분, 날씨를 영속화하고 도서 진도율 및 완독 상태를 자동 동기화. Core API는 01~05번 정량 통계(완독수, 총독서시간, 요일/시간대/날씨 분포, 최장 Streak, KDC 10대 장르 편독/다양성 지수, 스크랩 Top N 등) 집계를 전담하고 AI Agent가 사서 페르소나 텍스트 생성(06~07번)을 담당하는 하이브리드 아키텍처로 SSOT 및 $0 무과금 최적화 |

| 2026-09-15 | KDC 세부분류기호 기반 세부 주제(`subject`) 및 교보문고 CDN 고화질 표지 자동 폴백 도입, 화면 표시용 `display_genre` 제공 | 국립중앙도서관 API의 광범위한 대분류(문학 등) 대신 사용자가 선호하는 세부 장르(SF, 에세이, IT 등)를 화면에 우선 노출(`display_genre = subject or genre_name`)하여 UX를 극대화하고, AI 에이전트/프론트엔드의 국문/영문/코드 장르 입력을 유연하게 수용(`parse_to_genre_and_subject`). 또한 도서관 서지정보 표지 누락 시 교보문고 고화질 CDN(`contents.kyobobook.co.kr`)을 0ms 레이턴시로 자동 결합해 표지 누락을 원천 차단 |
| 2026-09-14 | 전사 레포 Squash and merge 단일 머지 전략 강제 및 커밋 메시지 자동화 (`PR_TITLE`, `BLANK`) | GitHub 기본 머지 커밋으로 인한 `Merge pull request #N...` 생성 및 개별 커밋 로그 덤프로 매번 수동 텍스트 편집이 강제되던 피로감 해소. `allow_merge_commit: false`, `allow_rebase_merge: false`, `squash_merge_commit_title: "PR_TITLE"`, `squash_merge_commit_message: "BLANK"`를 전사 레포에 적용하여, 검증된 PR 제목(`타입[적용범위]: 요약`)이 단일 커밋으로 깔끔하게 남고 본문은 기본 빈칸으로 생성되어 인간은 내용 확인 후 단 1회 클릭으로 머지를 완료할 수 있도록 최적화 |
| 2026-09-14 | 프론트엔드 연동용 개발자 간편 로그인(`POST /api/v1/auth/login`) 및 HttpOnly 쿠키 기반 세션 복원 지원 | 프론트엔드(`frontend-reader-web`)가 기존 이메일/비번 폼(`POST /auth/login`) 및 쿠키 기반 세션 복원(`/auth/refresh`)을 전제로 구현되어 있어, 소셜 OAuth 연동 설정 없이도 로컬에서 즉시 3D 서재/도서/사서 기능 E2E 테스트가 가능하도록 호환성 보장 (신규 가입 시 기본책장 및 대표 고양이 사서 자동 지급) |
| 2026-09-14 | 독서 진도율 100% 도달 시 COMPLETED 자동 전이 및 completed_at 기록, 국립중앙도서관 API 인메모리 TTL 캐싱(24h/1h) 및 Graceful Fallback 도입 | 진도율 100%임에도 수동으로 완독 상태를 변경해야 하던 UX 불편 및 완독 일시 미기록 문제 해소, 국립중앙도서관 외부 API 장애/타임아웃 시 사용자 검색 전체가 500 에러로 실패하는 취약점을 방지하고 반복 요청 외부 쿼터 절약 |
| 2026-09-14 | backend-auth 서비스를 backend-core-api로 병합 및 Google/Kakao 소셜 로그인 기반 자체 JWT 발급 체계로 전환 | Render 무료 티어(월 750시간) 인스턴스 소진 방지(백엔드 3개 10일 한계 -> 2개 15일 확보), AWS Cognito 종속성 완전 제거, httpx 기반 Google/Kakao 토큰 검증 및 자체 JWT 발급으로 구현 간소화, 회원 탈퇴 시 서재/기록 데이터 단일 트랜잭션 안전 삭제 보장 |
| 2026-09-13 | AWS Cognito 완전 배제 및 범용 Auth 서비스(Google OAuth 기반) JWT 연동 구조로 전환 | AWS 벤더 락인 해제 및 $0 무과금 아키텍처 실현. Core API는 Cognito 특정 클레임 종속성을 제거하고 표준 Bearer JWT(`sub`/`member_id` UUID 추출 및 유연한 서명 검증) 구조로 전환하여 독립성 확보 |
| 2026-09-12 | DPYB 바이브 코딩 하네스 표준 체계 도입 (`AGENTS.md`, `CLAUDE.md`, `.kiro/`, `.harness/`) | 여러 AI 코딩 툴(AGY, Claude Code, Codex, Kiro) 및 작업자 교체 시에도 동일한 컨텍스트와 워크플로우를 강제하고 문서 간 정보 중복/불일치 방지 |
| 2026-09-12 | 독서 감상 기록(Record) 및 스크랩 영속화 CRUD를 Core API로 통합 | AI 에이전트는 무상태(Stateless) 벡터 추론만 전담하고, 시스템의 영속 RDB CRUD 단일 진실 공급원(SSOT)을 Core API로 일원화하여 응집도 향상 |
| 2026-09-12 | 고양이 사서 대표 코드를 `CAT`으로 확정 (`RUSSIAN_BLUE` 레거시 별칭 호환) | 전사 스펙 최종본과의 일치 및 직관적인 네이밍 적용 |
| 2026-09-11 | `/health` 엔드포인트에서 Supabase `SELECT 1` 쿼리 실행 | Render 15분 무활동 슬립과 Supabase 7일 무쿼리 비활성화를 단 1회의 헬스체크 크론으로 동시 해결하여 $0 완전 무과금 상시 가동 달성 |
| 2026-09-11 | 단일 Supabase 인스턴스 내 PostgreSQL 스키마(`core`, `record`) 격리 | 무료 티어 1개 DB 비용($0)으로 서비스당 독립 DB(MSA) 원칙을 준수하고 타 서비스와의 물리적 결합 배제 |
| 2026-09-11 | 도서 정렬 키로 62진수 LexoRank(`ShelfRank`) 채택 | 정수 인덱스 방식의 대량 UPDATE 병목 방지 및 O(1) 중간 순서 재배치 보장, 공간 소진 시 균등 재분배(rebalance) 적용 |
| 2026-09-11 | 장르 한글명(`genreName`)을 DB 컬럼 대신 Pydantic `@computed_field`로 계산 | DB 내 중복 저장을 배제하고 응답 시 KDC 10대 대분류 코드로부터 한글 라벨("문학", "기술과학" 등) 동적 생성 |
| 2026-09-11 | 도서 메타데이터 수정 시 Full-Payload 방식(ADR-0006) 유지 | 도서 정보 갱신 시 의도치 않은 null 초기화 및 누락을 방지하고 프론트엔드 폼 상태와 1:1 동기화 보장 |
