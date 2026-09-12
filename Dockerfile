# ----------------------------------------------------
# 1단계: 빌더 스테이지 (의존성 패키징)
# ----------------------------------------------------
FROM python:3.12-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ----------------------------------------------------
# 2단계: 최종 런타임 스테이지 (경량 슬림 컨테이너)
# ----------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH

# 런타임에 필요한 최소 라이브러리만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 빌더 스테이지에서 설치된 python 패키지 복사
COPY --from=builder /root/.local /root/.local

# 애플리케이션 소스 코드 복사
COPY . .

# Render($PORT 동적 주입) 및 Cloud Run($PORT 동적 주입) 모두 호환
ENV PORT=8000
EXPOSE $PORT

# 헬스체크 probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# uvicorn 실행 (환경변수 PORT를 우선 바인딩)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
