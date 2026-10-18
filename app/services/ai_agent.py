import logging
from dataclasses import dataclass

import httpx

from app.config import settings
from app.core.kdc_mapper import parse_to_genre_and_subject
from app.models.enums import GenreType

logger = logging.getLogger(__name__)


@dataclass
class ClassifyGenreResult:
    genre: GenreType
    subject: str | None
    confidence: float | None
    source: str
    reason: str | None = None


class AiAgentClient:
    """
    AI 에이전트 서비스(POST /api/v1/classify-genre) 연동 비동기 클라이언트.
    - Gemini Flash-Lite 기반 장르 및 세부 주제어 2.5초 이내 정밀 판정.
    - 타임아웃, 네트워크 단절, HTTP 에러, 파싱 오류 시 500 에러 없이
      내부 KDC 십진분류 매퍼(parse_to_genre_and_subject)로 무중단 안전 폴백(Graceful Fallback).
    """

    DEFAULT_TIMEOUT_SECONDS = 2.5

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.AI_AGENT_BASE_URL or "").strip()

    def _fallback_kdc(
        self,
        title: str,
        kdc: str | None = None,
        reason: str | None = None,
    ) -> ClassifyGenreResult:
        """KDC 십진분류기호 및 도서명 기반 무중단 로컬 폴백"""
        fallback_genre, fallback_subject = parse_to_genre_and_subject(
            genre_input=kdc,
            current_subject=None,
            kdc_str=kdc,
            title=title,
        )
        return ClassifyGenreResult(
            genre=fallback_genre,
            subject=fallback_subject,
            confidence=None,
            source="KDC_FALLBACK",
            reason=reason,
        )

    async def classify_genre(
        self,
        title: str,
        author: str = "",
        description: str | None = None,
        kdc: str | None = None,
        isbn: str | None = None,
    ) -> ClassifyGenreResult:
        """
        AI Agent 서비스에 도서 장르 분류 요청.
        2.5초 하드 타임아웃 적용 및 실패 시 KDC 폴백 결과 반환.
        """
        clean_title = (title or "").strip()
        if not clean_title:
            return self._fallback_kdc(clean_title, kdc, reason="Title is empty")

        if not self.base_url:
            logger.info("AI_AGENT_BASE_URL 미설정으로 KDC 로컬 분류를 적용합니다.")
            return self._fallback_kdc(
                clean_title, kdc, reason="AI_AGENT_BASE_URL not set"
            )

        endpoint = f"{self.base_url.rstrip('/')}/api/v1/classify-genre"
        payload = {
            "title": clean_title,
            "author": (author or "").strip(),
            "description": (description or "").strip() or None,
            "kdc": (kdc or "").strip() or None,
            "isbn": (isbn or "").strip() or None,
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.DEFAULT_TIMEOUT_SECONDS
            ) as client:
                resp = await client.post(endpoint, json=payload)
                if resp.status_code != 200:
                    logger.warning(
                        f"AI Agent classify-genre HTTP {resp.status_code}: {resp.text}"
                    )
                    return self._fallback_kdc(
                        clean_title, kdc, reason=f"HTTP {resp.status_code}"
                    )

                data = resp.json()
                raw_genre = data.get("genre")
                subject = data.get("subject")
                confidence = data.get("confidence")
                source = data.get("source", "LLM")
                reason = data.get("reason")

                try:
                    genre_enum = GenreType(raw_genre)
                except (ValueError, TypeError):
                    logger.warning(f"AI Agent 알 수 없는 장르 코드 수신: {raw_genre}")
                    return self._fallback_kdc(
                        clean_title, kdc, reason=f"Unknown genre: {raw_genre}"
                    )

                return ClassifyGenreResult(
                    genre=genre_enum,
                    subject=subject.strip()
                    if isinstance(subject, str) and subject.strip()
                    else None,
                    confidence=float(confidence) if confidence is not None else None,
                    source=source if source in ("LLM", "KDC_FALLBACK") else "LLM",
                    reason=reason,
                )

        except httpx.TimeoutException:
            logger.warning(
                f"AI Agent classify-genre {self.DEFAULT_TIMEOUT_SECONDS}s 타임아웃 발생 (도서: {clean_title})"
            )
            return self._fallback_kdc(
                clean_title, kdc, reason="AI Agent request timed out"
            )
        except httpx.RequestError as e:
            logger.warning(f"AI Agent classify-genre 네트워크 통신 오류: {e}")
            return self._fallback_kdc(clean_title, kdc, reason=f"Network error: {e}")
        except Exception as e:
            logger.warning(f"AI Agent classify-genre 응답 처리 중 예외 발생: {e}")
            return self._fallback_kdc(clean_title, kdc, reason=f"Unexpected error: {e}")
