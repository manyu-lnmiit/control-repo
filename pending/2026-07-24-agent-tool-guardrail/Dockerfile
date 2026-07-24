FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agent_guardrail ./agent_guardrail
COPY policies ./policies
COPY pyproject.toml README.md ./
RUN mkdir -p /app/traces

RUN pip install --no-cache-dir .

EXPOSE 8080

ENV GUARDRAIL_POLICY_PATH=/app/policies/example_policy.yaml \
    GUARDRAIL_TRACE_PATH=/app/traces/service.jsonl

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=2)" || exit 1

CMD ["uvicorn", "agent_guardrail.service.app:app", "--host", "0.0.0.0", "--port", "8080"]
