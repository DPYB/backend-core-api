# BACKLOG (미해결 항목 및 기술 부채)

지금 하지 않지만 나중에 할 것들을 기록한다. 진행 중인 계획은 `PLAN.md`에 둔다.

- [ ] **PATCH 부분 수정(Partial Update) 옵션 검토**: 모바일 및 경량 클라이언트 요구 시 필요한 필드만 전송하는 PATCH Partial Update 지원 검토 (현재는 ADR-0006 Full-Payload)
- [ ] **소셜 로그인 프로덕션 설정 검증**: Google/Kakao Client ID 실환경 발급 및 프론트엔드 OAuth 리다이렉트 URI 매핑
- [ ] **LexoRank 배치 재분배 모니터링**: 대량 도서 등록 회원의 LexoRank 충돌 빈도 및 자동 재분배(`rebalanced_sequence`) 성능 모니터링
- [ ] **상용화 대비 8대 웹/인프라 보안 체계 구축**: 해커톤 종료 후 상용화를 위한 전사 3개 레포 8대 표준 보안 보완 (세부 계획: [`docs/SECURITY_ROADMAP.md`](file:///Users/jangchangho/backend-core-api/docs/SECURITY_ROADMAP.md) 참조)
  - Phase 1: 파일 업로드 10MB/매직바이트 가드, LLM/인증 Rate Limit, 프론트 .gitignore 보완
  - Phase 2: Supabase RLS 활성화, 보안 응답 헤더 미들웨어(HSTS/CSP), 토큰 블랙리스트
  - Phase 3: Dependabot/pip-audit 공급망 검사, 로그 PII 마스킹, 2FA 및 침해 웹훅

