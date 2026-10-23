# PLAN (미완료 계획)

본 레포에서 아직 안 끝난 계획과 체크리스트만 담는다. 완료된 항목은 STATE.md로 옮긴 뒤 제거한다.

## Phase 63: 글로벌 도서 검색 1단계 (Google Books 연동)
- [x] `app/services/google_books.py`: `GoogleBooksClient` 구현 (키워드/ISBN 검색, ISBN-13 우선, Cache-Control 준수, 429/타임아웃 장애 격리)
- [x] `app/services/google_books.py`: `lookup_by_isbn` 요청-응답 볼륨 간 ISBN 엄격 대조 및 불일치/누락 시 차단
- [x] `app/schemas/search.py`: `BookSearchItem.data_source` 필드 추가 및 `BookSearchResponse.books` computed field 직렬화 호환성 보장
- [x] `app/routers/search.py`: 키워드 및 ISBN 검색 시 잔여 Deadline(4.5s) 기반 Google Books 조건부 호출 + 기존 로컬 DB 검색 최종 유지
- [x] `tests/test_google_books.py`: 24종 신규 단위/통합 테스트 작성 및 기존 247개 회귀 테스트 통과 검증 (총 271개 100% 통과)
