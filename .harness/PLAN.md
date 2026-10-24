# PLAN (미완료 계획)

본 레포에서 아직 안 끝난 계획과 체크리스트만 담는다. 완료된 항목은 STATE.md로 옮긴 뒤 제거한다.
(각 과제는 [코드 구현] -> [자동 테스트] -> [스테이징 검증] -> [운영 인프라 확인] 4단계 완료 상태를 추적한다.)

---

## 1. [보안 P0] Phase 65: 자격증명 보안 강화 (Refresh Token Body 노출 제거 & 쿠키 단일화)
- [x] **사전 조사**: 백엔드 DTO 및 프론트엔드 실코드 전수 조사 완료 (Body 사용처 0건 확인)
- [x] **DTO 및 직렬화 정제**: `TokenResponse`, `LoginResponse`, `GuestLoginResponse` 응답 스키마에서 `refresh_token` 필드 완전 배제 (`access_token` / `accessToken` 듀얼 필드 유지)
- [x] **쿠키 발급 및 세션 수명주기 보존**: `_set_refresh_cookie` 및 `logout` 쿠키 만료/삭제 불변식 유지
- [x] **회귀 방지 테스트 검증**: `test_auth_credential_security.py` 7종 작성 및 전체 306개 단위 테스트 100% 그린
- **4단계 완료 상태 추적**:
  - [x] 코드 구현 완료
  - [x] 자동 테스트 통과 (기존 299개 + 신규 보안 회귀 테스트 100% 그린, 306 passed)
  - [ ] 스테이징 검증 완료 (프론트엔드 연동 E2E 확인)
  - [ ] 운영 인프라 확인 완료 (Cloud Run 배포 및 실환경 검증)

---

## 2. [보안 P0] Phase 65-2: 민감 정보 및 토큰 로그 노출 점검
- [ ] 백엔드 로깅(`app/core/logging.py`, `logs/app.log`) 및 전역 에러 핸들러의 JWT/개인정보 노출 여부 전수 감사
- [ ] 프론트엔드 콘솔 로그 및 오류 추적 시스템 내 민감정보 마스킹 가이드 동기화
- [ ] **4단계 완료 상태 추적**:
  - [ ] 코드 구현 완료 | [ ] 자동 테스트 통과 | [ ] 스테이징 검증 완료 | [ ] 운영 인프라 확인 완료

---

## 3. [데이터 계약] Phase 66: Google Books 원본 categories 직렬화 (Phase 63 2단계)
> ※ 보안 로드맵과 분리된 순수 도서 서지 데이터 계약 과제
- [ ] Core API `BookSearchItem.subject`로 Google Books `categories` 원본 직렬화 지원
- [ ] AI 에이전트 서비스 연계 시 장르 분류 1순위 힌트로 활용할 수 있도록 계약 고도화
- [ ] **4단계 완료 상태 추적**:
  - [ ] 코드 구현 완료 | [ ] 자동 테스트 통과 | [ ] 스테이징 검증 완료 | [ ] 운영 인프라 확인 완료

---

## 4. [보안 P1] Phase 67-A: Refresh Token Rotation 및 재사용 탐지 설계
- [ ] 동시 갱신 경쟁 조건(Race condition) 완화를 위한 Grace Period(유예 시간) 설계
- [ ] 탈취 토큰 재사용 감지 시 전체 활성 세션 일괄 무효화 정책 수립
- [ ] 로그아웃 블랙리스트 저장소(Redis vs DB) 선정 및 장애 시 폴백(Fail-open vs Fail-closed) 정의
- [ ] **4단계 완료 상태 추적**:
  - [ ] 설계 완료 | [ ] 코드 구현 완료 | [ ] 자동 테스트 통과 | [ ] 운영 인프라 확인 완료

---

## 5. [보안 P1] Phase 67-B: DB 접근 제어 및 Supabase RLS 조사·적용
- [ ] 백엔드 DB 커넥션 자격증명(`postgres` 슈퍼유저 vs 일반 유저) 및 Supabase PostgREST Data API 외부 노출 경로 선 조사
- [ ] Alembic 마이그레이션을 통해 `core.*`, `record.*`, `member.*` 전체 8개 테이블에 RLS(`ENABLE ROW LEVEL SECURITY`) 및 백엔드 무중단 엑세스 정책 적용
- [ ] **4단계 완료 상태 추적**:
  - [ ] 사전 조사 완료 | [ ] 코드 구현 완료 | [ ] 자동 테스트 통과 | [ ] 운영 인프라 확인 완료

---

## 6. [보안 P1] Phase 61 운영 미확인 인프라 신뢰 경계 추적 (인프라 체크리스트)
> ※ 코드 재구현이 아닌 '운영 확인' 상태 추적 항목
- [ ] Cloud Run 직접 URL 접근 차단 및 Cloudflare 프록시 경유 강제 방안 점검
- [ ] `CF-Connecting-IP` 신뢰 경계 일치 여부 확인
- [ ] 정상 사용자 이메일 Rate Limit 방해 여부 모니터링
- [ ] 멀티 인스턴스 스케일아웃 시 인메모리 Rate Limit 한계 대응 방안 정의

---

## 7. [보안 P2] Phase 68: 공급망 취약점 자동화 & 보안 모니터링
- [ ] CI 파이프라인(`ci.yml`)에 `pip-audit --strict` CVE 취약점 차단 단계 추가
- [ ] `.github/dependabot.yml` 등록 (주간 단위 보안 업데이트 자동 PR)
- [ ] 비정상 인증 시도 감지 Discord Webhook 알림 및 오탐 방지 임계치 수립
- [ ] **4단계 완료 상태 추적**:
  - [ ] 코드 구현 완료 | [ ] 자동 테스트 통과 | [ ] 스테이징 검증 완료 | [ ] 운영 인프라 확인 완료
