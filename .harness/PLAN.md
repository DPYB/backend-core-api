# PLAN (미완료 계획)

완료된 항목은 여기 체크만 남기지 않고 `STATE.md`로 옮긴 뒤 이 문서에서 제거한다.

## 실환경 인프라 연동 및 클라우드 배포
- [ ] Render Web Service에 본 레포지토리(Docker 환경) 배포 및 환경변수(`DATABASE_URL`, `NL_API_CERT_KEY`, `AUTH_APP_CLIENT_ID`, `CORS_ORIGINS`) 구성
- [ ] GitHub Actions Secrets 또는 Variables에 `RENDER_API_URL`을 등록하고 Keep-Alive 크론 정상 동작 여부 확인

## 타 서비스 연계 검증
- [ ] `backend-ai-agent` 서버에서 Core API(`GET /api/v1/librarians/representative`, `GET /api/v1/library/books`) Function Calling 연동 테스트
- [ ] Member 서비스 및 프론트엔드(`frontend-reader-web`)와의 실환경 API 계약(CORS, 토큰 서명) 교차 검증

