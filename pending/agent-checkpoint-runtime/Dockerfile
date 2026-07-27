FROM python:3.11-slim AS base

WORKDIR /app

# Install the package (no third-party runtime deps needed, but we install
# dev deps too so the same image can run tests/lint in CI-like contexts).
COPY pyproject.toml requirements.txt README.md ./
COPY agentflow ./agentflow
COPY examples ./examples
COPY tests ./tests

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]"

# Run the test suite at build time so a broken image fails to build.
RUN python -m pytest -q

ENV AGENTFLOW_DB_PATH=/data/agentflow.db
VOLUME ["/data"]

ENTRYPOINT ["agentflow"]
CMD ["--db", "/data/agentflow.db", "list"]
