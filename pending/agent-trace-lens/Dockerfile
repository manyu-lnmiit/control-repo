FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENT_TRACE_LENS_DB=/data/agent_trace_lens.db

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

RUN mkdir -p /data

EXPOSE 8000

ENTRYPOINT ["agent-trace-lens"]
CMD ["serve", "--db", "/data/agent_trace_lens.db", "--host", "0.0.0.0", "--port", "8000"]
