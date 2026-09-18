import time
from collections import defaultdict
from threading import Lock

from fastapi import Request

from app.core.exceptions import RateLimitExceededException


class InMemoryRateLimiter:
    """
    IP 기반 슬라이딩 윈도우 인메모리 Rate Limiter.
    신규 발급 vs 갱신 등 버킷별 독립 카운팅을 지원합니다.
    """

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> None:
        """
        주어진 key(예: 'ip:guest_issue')에 대해 window_seconds 동안 max_requests 초과 시
        RateLimitExceededException을 발생시킵니다.
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            # 윈도우 이전 타임스탬프 정리
            valid_timestamps = [t for t in self._requests[key] if t > window_start]
            if len(valid_timestamps) >= max_requests:
                raise RateLimitExceededException(
                    f"요청 한도({max_requests}회/{window_seconds}초)를 초과했습니다. 잠시 후 다시 시도해 주세요."
                )
            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps

    def clear(self) -> None:
        """테스트 격리를 위해 기록을 초기화합니다."""
        with self._lock:
            self._requests.clear()


guest_rate_limiter = InMemoryRateLimiter()


def get_client_ip(request: Request) -> str:
    """요청의 클라이언트 IP를 안전하게 추출합니다 (X-Forwarded-For 및 client.host 지원)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # 가장 앞쪽의 원본 클라이언트 IP 선택
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"
