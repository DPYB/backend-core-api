# BACKLOG (미해결 항목 및 기술 부채)

지금 하지 않지만 나중에 할 것들을 기록한다. 진행 중인 계획은 `PLAN.md`에 둔다.

- [ ] **Cognito 서명 검증 고도화**: 현재 토큰 디코딩 방식에서 Cognito JWKS 공개키 세트를 인메모리 캐싱하고 RSA 비대칭키 서명을 오프라인에서 엄격하게 검증하는 모듈 도입 검토
- [ ] **회원 탈퇴 시 데이터 정리 배치 API**: Member 서비스에서 회원 탈퇴(`WITHDRAWN`) 이벤트 발생 시, 해당 회원의 서재/도서/스크랩/사서 데이터를 일괄 정리하는 내부 전용 엔드포인트(`DELETE /internal/v1/members/{member_id}`) 구현
- [ ] **국립중앙도서관 API 응답 캐싱 레이어**: 동일 ISBN에 대한 외부 API 중복 호출을 줄이고 검색 응답 속도를 극대화하기 위해 Redis 또는 로컬 TTL 캐시 도입 검토
- [ ] **독서 상태-진도율 자동 동기화**: `current_page == total_pages` 도달 시 `reading_status`를 자동으로 `COMPLETED`로 전환하는 비즈니스 옵션 검토
- [ ] **PATCH 부분 수정(Partial Update) 옵션 검토**: 모바일 및 경량 클라이언트 요구 시 필요한 필드만 전송하는 PATCH Partial Update 지원 검토 (현재는 ADR-0006 Full-Payload)
