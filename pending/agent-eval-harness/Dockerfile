FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY pyproject.toml README.md ./
COPY agent_eval_harness ./agent_eval_harness
COPY examples ./examples

RUN pip install --no-cache-dir .

# Default entrypoint runs the CLI; pass args at `docker run` time, e.g.:
#   docker run --rm agent-eval-harness run --suite examples/tasks.yaml --agent mock
ENTRYPOINT ["agent-eval"]
CMD ["run", "--suite", "examples/tasks.yaml", "--agent", "examples.demo_agent:make_agent", "--store", "/tmp/runs.jsonl"]
