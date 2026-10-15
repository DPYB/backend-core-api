# PLAN (미완료 계획)

본 레포에서 아직 안 끝난 계획과 체크리스트만 담는다. 완료된 항목은 STATE.md로 옮긴 뒤 제거한다.

## [Feature] Phase 54: YES24 단건 조회 + AI Agent 장르 분류 연동 및 캐시 재사용 파이프라인

### 배경 및 목적
- AI 에이전트 서비스의 Gemini Flash-Lite 기반 `POST /api/v1/classify-genre` API 구축 완료에 맞춰, 본 레포(`backend-core-api`)의 도서 등록 및 서지 융합 파이프라인 연동.
- YES24(소개글/쪽수/표지) + 국립중앙도서관(KDC 힌트) + AI 장르 분류 클라이언트(장르/세부주제 정밀 판정) 삼각 결합 완성.
- 동일 ISBN 재등록 시 캐시 재활용으로 LLM 호출 최소화 및 개인 수정값 전파 방지(`genre_source != 'USER'`).

### 세부 작업 체크리스트
- [ ] Task 1: Alembic 마이그레이션 `011_add_genre_confidence` 작성 및 ORM/DTO 갱신 (`genre_confidence FLOAT NULL`)
- [ ] Task 2: `Yes24Client.lookup_by_isbn` 단건 조회 및 상품 상세 링크(`link`) 필드 지원
- [ ] Task 3: `AiAgentClient` 신설 및 2.5초 하드 타임아웃 / Graceful Fallback (`parse_to_genre_and_subject`) 구현
- [ ] Task 4: `BookService.create_book`에 동일 ISBN 캐시 재사용(`genre_source != 'USER'`) 및 AI 장르 융합 적용
- [ ] Task 5: `search.py`의 `_search_by_isbn` YES24 + 국립도서관 병렬 결합 개편
- [ ] Task 6: 단위/통합 테스트 작성 (`tests/test_ai_agent.py`, `tests/test_books.py`) 및 3-Tier 무결점 검증 (Ruff, Mypy, Pytest)

---

## [Infra] Google Cloud Run 배포 마이그레이션 & 운영 안정화

- [ ] Task 1: Google Cloud Run 배포 마이그레이션 가이드 및 워크플로우 구성
- [ ] Task 2: `YES_24_API_KEY` 실환경 환경변수 주입 및 컨테이너 기동 마이그레이션 검증
- [ ] Task 3: 데모 계정 자동 청소 크론(`.github/workflows/cleanup-demo.yml`) 주기 단축 및 게스트 리셋 연동


