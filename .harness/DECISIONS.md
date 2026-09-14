# DECISIONS (결정 히스토리, 최신 결정이 최상단)

결정 내용과 이유만 기록한다. 진행 상황은 `STATE.md`를 본다.

| 날짜 | 결정 | 이유 / 대안 비교 |
| :--- | :--- | :--- |
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
