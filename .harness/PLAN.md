# PLAN (미완료 계획)

## [Feature] 해커톤 공개 데모 계정 보호 & 쓰기 상한(Quota) 및 새벽 자동 리셋

### 배경 및 목적
- 해커톤 사이트에 공개된 데모 계정의 다중 동시 접속(3인 이상) 시 발생할 수 있는 데이터 오염, 계정 탈취(비밀번호/이메일 변경, 탈퇴), 시연 뷰 파괴를 방지.
- 게스트(Read-Only)와 차별화하여 심사위원의 쓰기 체험(도서 등록, 스크랩, 세션)을 온전히 보장하되, 무한 증식과 화면 오염을 막기 위한 **Allowlist 기반 쓰기 가드 + 도서/스크랩 상한(Quota) + 새벽 멱등 자동 리셋** 체계 구축.

### 핵심 설계 및 정책
1. **Allowlist 기반 데모 쓰기 가드 (FastAPI Route Template 매칭)**:
   - 토큰의 `sub`가 `settings.DEMO_MEMBER_ID`인 경우, 오직 허용된 라우트(`POST /api/v1/library/books`, `PATCH /api/v1/library/books/{book_id}/progress`, `POST /api/v1/library/books/{book_id}/scraps`, `POST /api/v1/reading-sessions` 등)만 쓰기 허용.
   - 비밀번호 변경(`POST /auth/password/change`), 회원 탈퇴(`DELETE /users/me`), 프로필 변경(`PATCH /users/me`), 도서 삭제 등은 즉시 `403 Forbidden` (`DEMO_ACCOUNT_PROTECTED`).
2. **도서/스크랩 상한 (Quota Guard)**:
   - 데모 계정 활성 도서(`deleted_at IS NULL`) 최대 25권 제한. 초과 시 `403 Forbidden` (`DEMO_QUOTA_EXCEEDED`).
   - 도서당 활성 스크랩 최대 10개, 독서 세션 최대 10개 제한.
3. **관리자 보호 리셋 엔드포인트 (`POST /api/v1/admin/demo/reset`)**:
   - `X-Admin-Key` 헤더 인증 필수 (데모 일반 토큰 호출 불가).
   - 시드 데이터 외 추가된 도서/스크랩/세션을 트랜잭션 내에서 일괄 정리하고, 시연 도서의 진도율을 시드 정의 기준값으로 멱등하게 복구.
4. **GitHub Actions 새벽 4시 자동 워크플로우 (`.github/workflows/cleanup-demo.yml`)**:
   - 매일 KST 04:00 (UTC 19:00) 스케줄 + `workflow_dispatch` 수동 트리거 지원.
   - Render 콜드스타트 워밍 핑(60s 타임아웃 및 재시도) 후 관리자 리셋 엔드포인트 호출.

---

### 체크리스트

#### Phase 3: GitHub Actions 새벽 리셋 워크플로우 구축
- [ ] `.github/workflows/cleanup-demo.yml`: KST 04:00 크론 + Render 웜업 핑 + 관리자 리셋 API 호출 및 실패 알림 구성

#### Phase 4: 전체 시스템(Frontend/AI Agent/운영) 연동 체크
- [ ] 자격증명 노출 회수 (해커톤 제출 폼/문서 비공개 처리 또는 수정)
- [ ] `backend-ai-agent`: 사서 대화 Redis 세션 키 `chat:{user_id}:{session_id}` 및 24h TTL 확인
- [ ] `backend-ai-agent`: Gemini 전역 호출 상한 및 429 서킷브레이커/안내 문구 폴백 확인
- [ ] 발표/심사 당일용 독립 비공개 계정 사전 확보
