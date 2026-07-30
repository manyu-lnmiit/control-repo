# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app

# Install the package with the optional HTTP API extra so the container
# can serve prompt-registry over HTTP out of the box.
COPY pyproject.toml ./
COPY src ./src
COPY README.md ./

RUN pip install --no-cache-dir ".[api]"

ENV PROMPT_REGISTRY_DB=/data/prompt_registry.db
VOLUME ["/data"]

EXPOSE 8000

# Default: run the HTTP API. Override the command to use the CLI instead, e.g.:
#   docker run --rm -v prompt-data:/data prompt-registry \
#     prompt-registry --db /data/prompt_registry.db log my-prompt
CMD ["uvicorn", "prompt_registry.api:app", "--host", "0.0.0.0", "--port", "8000"]
