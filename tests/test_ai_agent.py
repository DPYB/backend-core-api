import httpx
import pytest

from app.models.enums import GenreType
from app.services.ai_agent import AiAgentClient


@pytest.mark.asyncio
async def test_classify_genre_success(monkeypatch: pytest.MonkeyPatch):
    """AI Agent 서비스 정상 200 OK 응답 시 LLM 분류 결과 반환 검증"""
    client = AiAgentClient(base_url="https://mock-ai-agent.com")

    async def mock_post(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={
                "genre": "PHILOSOPHY",
                "subject": "미술치료/심리",
                "confidence": 0.95,
                "source": "LLM",
                "reason": "미술을 통한 심리 치유 도서",
            },
            request=req,
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await client.classify_genre(
        title="그림의 힘",
        author="김선현",
        description="그림을 통해 마음을 치유하는 명화 테라피",
        kdc="513.8",
        isbn="9788950958749",
    )

    assert result.genre == GenreType.PHILOSOPHY
    assert result.subject == "미술치료/심리"
    assert result.confidence == 0.95
    assert result.source == "LLM"
    assert result.reason == "미술을 통한 심리 치유 도서"


@pytest.mark.asyncio
async def test_classify_genre_timeout_fallback(monkeypatch: pytest.MonkeyPatch):
    """AI Agent 호출 중 2.5초 타임아웃 발생 시 500 없이 KDC 로컬 폴백 반환 검증"""
    client = AiAgentClient(base_url="https://mock-ai-agent.com")

    async def mock_timeout(self, url, **kwargs):
        raise httpx.TimeoutException("Connection timed out after 2.5s")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_timeout)

    # 513.8은 KDC 매퍼 상 PHILOSOPHY(철학/심리치료)로 승격되는 코드
    result = await client.classify_genre(
        title="그림의 힘",
        author="김선현",
        kdc="513.8",
        isbn="9788950958749",
    )

    assert result.genre == GenreType.PHILOSOPHY
    assert result.source == "KDC_FALLBACK"
    assert result.confidence is None
    assert "timed out" in (result.reason or "")


@pytest.mark.asyncio
async def test_classify_genre_http_error_fallback(monkeypatch: pytest.MonkeyPatch):
    """AI Agent가 500 Internal Error 또는 429 Too Many Requests 반환 시 KDC 폴백 검증"""
    client = AiAgentClient(base_url="https://mock-ai-agent.com")

    async def mock_error(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(500, text="Internal Server Error", request=req)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_error)

    # 813.6 한국 소설 KDC 코드
    result = await client.classify_genre(
        title="모순",
        author="양귀자",
        kdc="813.6",
    )

    assert result.genre == GenreType.LITERATURE
    assert result.source == "KDC_FALLBACK"
    assert result.confidence is None
    assert "HTTP 500" in (result.reason or "")


@pytest.mark.asyncio
async def test_classify_genre_invalid_genre_response(monkeypatch: pytest.MonkeyPatch):
    """AI Agent가 스키마에 없는 불법 장르명을 반환할 때 KDC 폴백 검증"""
    client = AiAgentClient(base_url="https://mock-ai-agent.com")

    async def mock_invalid(self, url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={
                "genre": "ILLEGAL_GENRE_NAME",
                "subject": "미지의 장르",
                "confidence": 0.5,
                "source": "LLM",
            },
            request=req,
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_invalid)

    result = await client.classify_genre(
        title="수학의 정석",
        kdc="410",
    )

    assert result.genre == GenreType.NATURAL_SCIENCE
    assert result.source == "KDC_FALLBACK"
    assert "Unknown genre" in (result.reason or "")


@pytest.mark.asyncio
async def test_classify_genre_missing_base_url():
    """AI_AGENT_BASE_URL 미설정 시 네트워크 호출 없이 즉시 KDC 로컬 폴백 반환 검증"""
    client = AiAgentClient(base_url="")

    result = await client.classify_genre(
        title="총 균 쇠",
        kdc="300",
    )

    assert result.genre == GenreType.SOCIAL_SCIENCE
    assert result.source == "KDC_FALLBACK"
    assert "not set" in (result.reason or "")


@pytest.mark.asyncio
async def test_classify_genre_empty_title():
    """빈 제목 입력 시 즉시 KDC 로컬 폴백 반환 검증"""
    client = AiAgentClient(base_url="https://mock-ai-agent.com")

    result = await client.classify_genre(
        title="",
        kdc="900",
    )

    assert result.genre == GenreType.HISTORY
    assert result.source == "KDC_FALLBACK"
    assert "empty" in (result.reason or "")
