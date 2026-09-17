# STATE (완료 스냅샷)

단계가 끝나면 그 단계를 한 줄로 갱신한다. 세션별 서술은 `HANDOFF.md`에 남긴다.

## 완료된 단계
- **Phase 1 (환경 & 인프라)**: Python 3.12, FastAPI, SQLAlchemy 2.0 (asyncpg), Alembic 기반 아키텍처 및 Supabase `core` 스키마 비동기 세션 구성 완료
- **Phase 2 (서재 & 도서 도메인)**: 책장(Shelf, 기본책장 자동생성/이관), 서재 도서(LibraryBook 11개 필드 수정, 진도율, Soft Delete), 문장 스크랩(Scrap) 도메인 및 API 구현 완료
- **Phase 3 (정렬 & 외부 연동)**: 62진수 LexoRank(`ShelfRank`) 사전식 순서 재배치 알고리즘, KDC 10대 대분류 한글 라벨 매퍼, 국립중앙도서관 서지정보 비동기 검색 클라이언트 구현 완료
- **Phase 4 (사서 캐릭터 도메인)**: 동물 사서 4종(`CAT`, `SHOEBILL`, `SEA_SLUG`, `GECKO`) 마스터 카탈로그, 획득, 개명, 방출, 단일 대표 사서 라이프사이클 API 구현 완료
- **Phase 5 (보안 & 에러 규격)**: Cognito Access Token(`sub` UUID 변환) 인증 및 18종 표준 에러 응답 규격(`{"code": ..., "message": ...}`) 전역 핸들러 구현 완료
- **Phase 6 (무과금 배포 최적화)**: 경량 멀티스테이지 Dockerfile, 핫리로드 compose, `/health` Supabase `SELECT 1` 연동 및 14분 주기 GitHub Actions Keep-Alive 워크플로우 구성 완료
- **Phase 7 (독서 감상 기록 통합)**: `record` 스키마 기반 독서 기록(Record) & 스크랩 CRUD, Soft Delete Cascade 및 AI 벡터화 비동기 연동 완료 (총 44개 테스트 100% Pass)
- **Phase 8 (바이브 코딩 하네스)**: DPYB 표준 하네스 체계(`AGENTS.md`, `CLAUDE.md`, `.kiro/`, `.harness/` 6개 문서) 구축 완료
- **Phase 9 (중앙 Reusable CI & 개발 표준 최신화)**: Reusable 워크플로우 2종(`ci.yml`, `lint-pr.yml`) 연동, 개별 keep-alive 워크플로우 삭제, /health SELECT 1 보장 확인, 최신 개발 표준(feat/* 단일화, [scope] 대괄호 규격, 인간 직접 머지 원칙, 독서기록 RDBMS 영속화 core-api 전담 소유) 하네스 문서 전면 동기화 완료
- **Phase 10 (develop 브랜치 분할 커밋 & 원격 푸시)**: DPYB 커밋 규격(`타입[적용범위]: 요약`) 준수 8단계 원자적 분할 커밋 및 `origin/develop` 브랜치 푸시 완료
- **Phase 11 (실환경 Supabase 마이그레이션 적용)**: Supabase 서울 리전 실제 DB 인스턴스 연동, 특수문자 대응 개별 DB 환경변수 지원, Alembic 마이그레이션 성공(`core`, `record` 스키마 및 8개 테이블/시드 데이터 생성 검증) 완료
- **Phase 12 (backend-auth 병합 & 소셜 로그인 통합)**: AWS Cognito 종속성 완전 제거, `member` 스키마(회원, 약관, 약관동의) DDL 및 Alembic `003_add_member_schema` 적용, Google/Kakao 소셜 로그인 및 자체 Bearer JWT 발급/갱신, 프로필 조회/수정 및 회원 탈퇴 시 서재·도서·독서기록·사서 Cascade 일괄 소프트 삭제 구현 완료 (총 50개 테스트 100% Pass)
- **Phase 13 (독서 진도율 자동 동기화 & 국립중앙도서관 캐싱/내결함성)**: 독서 진도율 100% 도달 시 COMPLETED 자동 전이 및 완독일시(`completed_at`) 자동 기록/리셋 로직(Alembic `004_add_completed_at_to_library_book`), 국립중앙도서관 API 인메모리 TTL 캐싱(24h/1h) 및 외부 타임아웃/장애 Graceful Fallback 구축 완료 (총 58개 테스트 100% Pass)
- **Phase 14 (조직 공통 PR 템플릿 미니멀 Type B 통일 및 완전 중앙화)**: DPYB 조직 레포(`.github`)의 PR 템플릿을 미니멀 Type B 구조(요약, 적용 범위, 바이브코딩 고려사항/리뷰포인트, 필수 체크리스트)로 다이어트하고, `backend-core-api` 자체 중복 파일을 제거하여 DPYB 전사 3개 레포(`frontend-reader-web`, `backend-core-api`, `backend-ai-agent`)가 `.github`로부터 자동 상속받도록 중앙화 완료
- **Phase 15 (프론트엔드 호환 개발용 간편 로그인 & 쿠키 세션 지원)**: 프론트엔드(`frontend-reader-web`) 로컬 연동을 위한 `POST /api/v1/auth/login` 엔드포인트 구현(이메일 기반 자동 가입 및 기본 책장/고양이 사서 CAT 자동 지급), camelCase/snake_case 듀얼 토큰 직렬화, HttpOnly 쿠키 기반 토큰 갱신(`/auth/refresh`) 및 세션 유지, CORS 로컬 프론트엔드 regex 지원 완료 (총 61개 테스트 100% Pass)
- **Phase 16 (전사 레포 Squash 머지 단일화 & 원클릭 컨벤션 자동화)**: DPYB 전사 4개 레포(`backend-core-api`, `backend-ai-agent`, `frontend-reader-web`, `.github`)에 `Allow merge commits` 및 `Rebase` 차단, `Squash and merge` 단일화, PR 제목(`PR_TITLE`) 자동 매핑, 본문 빈칸(`BLANK`) 기본 설정, 머지 후 피처 브랜치 자동 삭제(`delete_branch_on_merge`) 일괄 적용 완료. DPYB 공통 문서(`docs/02-git-conventions.md`) 및 자동화 스크립트(`setup-branch-protection.sh`) 업데이트 완료
- **Phase 17 (PR 본문 '고려사항 & 리뷰 포인트' 섹션 필수 검증 반영)**: DPYB 중앙 CI(`reusable-pr-lint.yml`) 및 템플릿에 `## 💬 고려사항 & 리뷰 포인트`를 필수 4대 섹션으로 승격, 빈칸 방치 검증 로직 추가 및 '해당 없음'/'특이사항 없음' 허용 가이드 반영 완료
- **Phase 18 (KDC 세부 주제 파서 & 교보문고 CDN 표지 폴백 강화)**: KDC 세부분류기호 기반 세부 주제(`subject`: SF, 에세이, 소설, IT 등) 자동 추출 및 사용자 화면 최우선 표시용 `display_genre` 필드 제공, 국문/영문/코드 다국어 장르 스마트 파싱(`parse_to_genre_and_subject`), 도서관 API 및 도서 등록 시 교보문고 고화질 CDN(`contents.kyobobook.co.kr`) 0ms 표지 폴백 구축 완료 (총 67개 테스트 100% Pass)
- **Phase 19 (사서 월간 독서 리포트 통계 집계 API & 스톱워치 독서 세션 연동)**: 불필요한 '중단' 상태를 배제하고 기존 3단계 체제 유지, Alembic `005_add_reading_session_and_weather` 마이그레이션(날씨 컬럼 및 `record.reading_sessions` 신설), 스톱워치 종료 시 `POST /api/v1/reading-sessions` 단일 호출로 독서시간·페이지·날씨 영속화 및 도서 진도율/완독 자동 동기화, `GET /api/v1/reports/monthly-stats` 엔드포인트를 통한 01~05번 정량 통계(완독수, 누적페이지, 총시간, 요일/시간대/날씨 분포, 최장 Streak, KDC 10대 장르 다양성/편독 지수, 상위 스크랩 도서, 완독/읽는중 도서 등) 전수 집계 구현 완료 (총 74개 테스트 100% Pass)
- **Phase 20 (사서 4종 페르소나 및 기본 표시명 동기화)**: AI 에이전트 서비스 규격에 맞춰 사서 4종(`CAT`="블루", `SHOEBILL`="슈빌", `SEA_SLUG`="누디", `GECKO`="게코") 페르소나 메타데이터(MBTI, 담당 장르, 설명, 종결어미) 및 기본 표시명 매핑(`DEFAULT_LIBRARIAN_NAMES`) 구축, `GET /api/v1/librarian-types` 응답에 메타데이터 통합 반환, 사서 획득 시 이름 생략 시 기본 표시명 자동 폴백, `GET /api/v1/members/me` 및 `GET /api/v1/users/me` 프로필 응답에 대표 사서 정보(`librarian_type`, `librarian_name`, `librarian_default_name`) 통합 완료 (총 77개 테스트 100% Pass)
- **Phase 21 (타 서비스 통신 계약 및 통합 연계 완결)**: `frontend-reader-web` 및 `backend-ai-agent` 통신 계약 전수 분석 및 완벽 호환 보장: 페이징 응답 DTO에 프론트엔드 호환 `books` 및 `scraps` 필드 듀얼 직렬화(`LibraryBookPageResponse`, `ScrapPageResponse`), 도서 단건 조회 별칭 엔드포인트(`GET /api/v1/books/{book_id}`) 추가, 도서 검색(`GET /api/v1/books/search`)에서 ISBN 및 키워드 통합 검색과 선택적 인증(`get_optional_member_id`) 지원, 소셜 로그인 응답에 회원 프로필(`member`) 즉시 반환 지원 (Core API 81개 테스트 100% Pass, AI Agent 100개 테스트 100% Pass, Frontend 빌드 성공 검증)
- **Phase 22 (소셜 로그인 실환경 스펙 확정 및 환경변수 템플릿 정비)**: Google OAuth 2.0 Web Client ID(`GOOGLE_CLIENT_ID`) 및 Kakao REST API Key/Client ID(`KAKAO_CLIENT_ID`) 실환경 설정 스펙 확정, Render 배포용 `.env.example` 템플릿(Supabase Pooler, JWT, OAuth, 외부 API, CORS) 전면 정비 완료
- **Phase 23 (중앙 Git Hooks 표준 연동)**: `.githooks/pre-commit` 등록 및 `core.hooksPath .githooks` 바인딩, 코드 변경 시 STATE.md 동반 갱신 알림 훅 검증 완료
- **Phase 24 (KDC 800번대 KDC 6판 표준화 & 외국 SF 소설 스마트 오버라이드)**: DDC 혼동 버그를 바로잡아 KDC 제6판 기준 800번대 문학 세부분류(810 한국, 820 중국, 830 일본, 840 영미, 850 독일, 860 프랑스 등) 전면 교정, KDC 외국소설 장르 미분류 한계를 극복하기 위해 《마션》·《헤일메리》 등 도서 제목/설명 SF 키워드 기반 `SF/과학소설` 스마트 오버라이드 및 대분류 승격 로직 구축 완료 (총 83개 테스트 100% Pass)
- **Phase 25 (화면 노출 우선순위 Subject 1순위 보장 & 510번대 치료/건강 라우팅 보강)**: 프론트엔드가 `genreName` 또는 `displayGenre` 어느 필드를 참조하더라도 세부 주제(`subject`)가 존재할 때 1순위로 노출되도록 DTO 2중 방어 조치 구현, KDC 513.8(미술치료/심리요법) 및 키워드("미술치료", "그림의 힘", "심리치료") 스마트 오버라이드 연동, 콘솔+회전 파일 듀얼 로깅(`logs/app.log`) 구축 완료 (총 83개 테스트 100% Pass)



