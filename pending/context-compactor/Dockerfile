FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir ".[api]"

COPY tests ./tests
COPY examples ./examples

EXPOSE 8000

# Default: run the optional HTTP compaction service.
# Override the command to use the CLI instead, e.g.:
#   docker run --rm -v $(pwd):/data context-compactor \
#     context-compactor compact /data/transcript.jsonl --max-tokens 2000
CMD ["uvicorn", "context_compactor.api:app", "--host", "0.0.0.0", "--port", "8000"]
