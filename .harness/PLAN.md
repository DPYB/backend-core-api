# PLAN (미완료 계획)

완료된 항목은 여기 체크만 남기지 않고 `STATE.md`로 옮긴 뒤 이 문서에서 제거한다.

## 1. 로컬 풀스택 E2E 연동 검증
- [ ] Core API 로컬 서버 구동 (`http://127.0.0.1:8000`)
- [ ] AI Agent 서버 로컬 구동 (`http://127.0.0.1:8001`, `CORE_API_BASE_URL=http://127.0.0.1:8000`)
- [ ] Frontend Web 개발 서버 연동 및 로그인/서재/사서채팅 E2E 검증

## 2. 실환경 인프라 배포 및 무과금($0) 상시 가동 검증
- [ ] Render Web Service 신규 생성 및 Dockerfile 기반 배포 설정 (동적 `$PORT` 바인딩)
- [ ] Render 환경변수 구성 (`DATABASE_URL` 또는 개별 `DB_*`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `NL_API_CERT_KEY` 등)
- [ ] 실환경 배포 인스턴스 헬스체크 (`GET /health`) 호출을 통한 Supabase `SELECT 1` 및 무과금 Keep-Alive 동작 확인
- [ ] 중앙 `DPYB/.github` 킵얼라이브 워크플로우에 Render Core API 헬스체크 엔드포인트 연동 점검

## 3. 타 서비스 통신 계약 및 통합(E2E) 연계 검증
- [ ] `backend-ai-agent` 서비스와의 Function Calling 연동 테스트 (사서 조회, 서재 도서 목록 조회, 월간 통계 수신 및 06/07 AI 리포트 생성)
- [ ] `frontend-reader-web` 실환경 CORS 및 스톱워치 세션/날씨 전송/월간 리포트 뷰 E2E 검증




