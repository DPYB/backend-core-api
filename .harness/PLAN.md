# PLAN (미완료 계획)

완료된 항목은 여기 체크만 남기지 않고 `STATE.md`로 옮긴 뒤 이 문서에서 제거한다.

## 1. 실환경 인프라 배포 및 무과금($0) 상시 가동 검증
- [ ] Render Web Service 신규 생성 및 Dockerfile 기반 배포 설정 (동적 `$PORT` 바인딩)
- [ ] Render 환경변수 등록 (`DB_*`, `JWT_*`, `GOOGLE_*`, `KAKAO_*`, `CORS_ORIGINS`, `NL_API_CERT_KEY`) 및 실환경 배포
- [ ] 실환경 배포 인스턴스 헬스체크 (`GET /health`) 호출을 통한 Supabase `SELECT 1` 및 무과금 Keep-Alive 동작 확인
- [ ] 중앙 `DPYB/.github` 킵얼라이브 워크플로우에 Render Core API 헬스체크 엔드포인트 연동 점검
