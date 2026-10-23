# PLAN (미완료 계획)

본 레포에서 아직 안 끝난 계획과 체크리스트만 담는다. 완료된 항목은 STATE.md로 옮긴 뒤 제거한다.

## 후속 작업 계획

### 1. Google Cloud Run 운영 환경 배포 및 키 주입 점검
- [ ] Google Cloud Run 콘솔에 `GOOGLE_BOOKS_API_KEY` 환경변수 주입
- [ ] 스테이징/운영 배포 후 라이브 원서 검색 및 표지/메타데이터 연동 점검

### 2. Google Books 원본 categories 직렬화 후속 과제 (Phase 63 2단계)
- [ ] Core API `BookSearchItem.subject`로 Google Books `categories` 원본 직렬화 지원
- [ ] AI 에이전트 서비스 연계 시 힌트로 활용할 수 있도록 계약 고도화

### 3. 크로스 서비스 데이터 계약 동기화
- [ ] AI 에이전트 서비스: `CLASSIFY_GENRE_SYSTEM_PROMPT`에서 KDC/DDC 분리 기준 명시 및 `subject` 필수 도출 규칙 반영
- [ ] 프론트엔드 웹: 도서 칩 노출 시 `displayGenre || subject || genreLabel(genre)` 우선순위 통일
