# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir ".[api]"

COPY tests ./tests

# Default entrypoint runs the CLI; override the command to instead run the
# FastAPI service, e.g.:
#   docker run --rm -p 8080:8080 injection-radar \
#     uvicorn injection_radar.api:app --host 0.0.0.0 --port 8080
ENTRYPOINT ["injection-radar"]
CMD ["--help"]
