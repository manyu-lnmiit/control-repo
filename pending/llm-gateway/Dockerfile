FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

COPY config.example.yaml ./config.example.yaml

EXPOSE 8000

ENV LLM_GATEWAY_CONFIG=/app/config.example.yaml

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["llm-gateway", "serve", "--host", "0.0.0.0", "--port", "8000"]
