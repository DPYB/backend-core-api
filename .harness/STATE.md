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

