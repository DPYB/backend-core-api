# PLAN (미완료 계획)

완료된 항목은 여기 체크만 남기지 않고 `STATE.md`로 옮긴 뒤 이 문서에서 제거한다.

## 1. 실환경 인프라 배포 및 무과금($0) 상시 가동 검증
- [ ] Render Web Service 신규 생성 및 Dockerfile 기반 배포 설정 (동적 `$PORT` 바인딩)
- [ ] Render 환경변수 구성 (`DATABASE_URL` 또는 개별 `DB_*`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `NL_API_CERT_KEY` 등)
- [ ] 실환경 배포 인스턴스 헬스체크 (`GET /health`) 호출을 통한 Supabase `SELECT 1` 및 무과금 Keep-Alive 동작 확인
- [ ] 중앙 `DPYB/.github` 킵얼라이브 워크플로우에 Render Core API 헬스체크 엔드포인트 연동 점검

## 2. 도메인 기능 고도화 및 편의 비즈니스 로직
- [ ] **독서 진도율 자동 동기화 로직 구현**: `current_page == total_pages` 도달 시 `reading_status`를 `COMPLETED`로 자동 전이 및 완독일시(`completed_at`) 설정
- [ ] **국립중앙도서관 API 통신 안정성 강화**: 타임아웃, 예외 발생 시 Graceful Fallback 및 동일 ISBN 요청 인메모리/TTL 캐싱 검토

## 3. 타 서비스 통신 계약 및 통합(E2E) 연계 검증
- [ ] `backend-ai-agent` 서비스와의 Function Calling 연동 테스트 (사서 조회, 서재 도서 목록 조회)
- [ ] `frontend-reader-web` 실환경 CORS 및 소셜 로그인/JWT 토큰 추출 교차 검증
