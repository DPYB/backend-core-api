# PLAN (미완료 계획)

## [Deployment & Operations] 게스트 체험 모드 배포 및 타 레포 연동 계획

### 체크리스트
- [ ] Phase 1 (AI Agent 선배포): `backend-ai-agent`에서 게스트 토큰(`role: guest`) 대상 대화 턴수 제한 및 게스트 전역 일일 LLM 호출 상한(비상 서킷브레이커) 배포
- [ ] Phase 2 (Core API 배포): `ENABLE_GUEST_WRITE=False` 기본값 상태로 배포하여 잠정 안정화
- [ ] Phase 3 (Frontend 배포): `frontend-reader-web` 상단 공용 서재 안내 띠 배너 배포
- [ ] Phase 4 (게스트 쓰기 활성화): Cloud Run / Render 환경변수 `ENABLE_GUEST_WRITE=True` 적용으로 실환경 개방
- [ ] 운영 리셋 확인: 게스트 서재 정리 필요 시 `POST /api/v1/admin/demo/reset?target=guest` 호출 동작 확인
- [ ] 시연 리셋 확인: 발표 전 시연 서재 복원 시 `POST /api/v1/admin/demo/reset?target=demo` 호출 동작 확인






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

#### Phase 4: 전체 시스템(Frontend/AI Agent/운영) 연동 체크
- [ ] 자격증명 노출 회수 (해커톤 제출 폼/문서 비공개 처리 또는 수정)
- [ ] `backend-ai-agent`: 사서 대화 Redis 세션 키 `chat:{user_id}:{session_id}` 및 24h TTL 확인
- [ ] `backend-ai-agent`: Gemini 전역 호출 상한 및 429 서킷브레이커/안내 문구 폴백 확인
- [ ] 발표/심사 당일용 독립 비공개 계정 사전 확보

---

## [Feature] Google Cloud Run 배포 마이그레이션 & Gmail SMTP 이메일 인증 연동

### 배경 및 목적
1. **Google Cloud Run 마이그레이션**: Render 무료 인스턴스의 슬립/콜드스타트 한계를 극복하고, Google Cloud 인프라(Cloud Run 월 200만 건 무료 요청 티어)로 전환하여 안정적인 $0 고성능 운영 환경 구축.
2. **Gmail SMTP 이메일 인증 연동**: 회원가입 시 실제 실존하는 이메일인지 검증하여 타인 도용 및 가짜 계정 생성을 원천 차단하고, 6자리 인증 코드 발송/검증 프로세스를 완성.

### 세부 설계

#### 1. Gmail SMTP 인증 메일 발송 시스템
- **의존성 & 환경설정**: `aiosmtplib` 비동기 라이브러리 추가, `app/config.py`에 SMTP 설정(`SMTP_HOST="smtp.gmail.com"`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_NAME="DontPawGet 사서단"`) 추가.
- **인증 데이터 영속화**:
  - `member.email_verifications` 테이블 생성 (Alembic 마이그레이션): `email`, `code`, `expires_at`(발급 후 5분), `is_verified`, `created_at`.
  - 또는 `member.members`에 `is_verified BOOLEAN DEFAULT FALSE` 컬럼 추가.
- **비즈니스 로직**:
  - `EmailService`: HTML 템플릿(예쁜 서비스 로고와 사서 디자인의 6자리 인증 코드 메일) 기반 비동기 발송 로직 구현.
  - `POST /api/v1/auth/signup`: 회원 등록 및 6자리 난수 코드 생성 후 Gmail SMTP 백그라운드 태스크 발송 (미인증 상태).
  - `POST /api/v1/auth/signup/confirm`: 실제 코드 일치 및 5분 유효시간 검증 ➔ 통과 시 `is_verified=True` 승인.
  - `POST /api/v1/auth/signup/resend`: 재발송 요청 시 기존 미인증 코드 갱신 및 재발송 (Rate Limit 분당 1회 방어).
  - `POST /api/v1/auth/login`: `is_verified`가 False인 경우 `403 EMAIL_NOT_VERIFIED` 반환하여 인증 강제.

#### 2. Google Cloud Run 마이그레이션 구성
- **Dockerfile 점검**: 이미 `${PORT:-8000}` 동적 바인딩 및 슬림 2단계 빌드가 완비되어 있어 Cloud Run 즉시 호환.
- **배포 가이드 & 스크립트 작성**:
  - Google Cloud CLI(`gcloud run deploy`) 명령 및 환경변수 주입 스펙 문서화.
  - GitHub Actions를 통한 Cloud Run 자동 배포 워크플로우 구성 방안 제시.
- **CORS 및 DNS 도메인 연동**:
  - Cloud Run 생성 URL 또는 커스텀 도메인에 대한 프론트엔드 연동 및 Cloudflare CDN 설정 가이드.

### 체크리스트
- [x] Task 1: `aiosmtplib` 의존성 추가 및 `app/config.py`에 Gmail SMTP 환경변수 정의
- [x] Task 2: Alembic 마이그레이션 작성 (`009_add_email_verifications.py` 및 `EmailVerification` 모델)
- [x] Task 3: `EmailService` 구현 (사서 컨셉 HTML 인증 메일 템플릿 및 Gmail SMTP 비동기 전송)
- [x] Task 4: `MemberService` & `auth.py` 회원가입/인증/재발송/로그인 플로우에 실제 이메일 인증 연동
- [x] Task 5: 단위 및 통합 테스트 갱신 (`test_signup.py`, 112개 테스트 100% 통과)
- [x] Task 6: 환경변수 템플릿(`.env.example`)에 Gmail SMTP 항목 반영
- [ ] Task 7: Google Cloud Run 배포 마이그레이션 가이드 및 워크플로우 구성




