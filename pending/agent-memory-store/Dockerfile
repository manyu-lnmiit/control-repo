FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENT_MEMORY_DB=/data/agent_memory.db

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir ".[server]" \
    && mkdir -p /data

EXPOSE 8000

# Default: run the optional HTTP API. Override the command to use the CLI
# instead, e.g.:
#   docker run --rm -it agent-memory-store agent-memory-store stats
ENTRYPOINT ["agent-memory-store"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
