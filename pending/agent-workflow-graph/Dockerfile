FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY src ./src
COPY examples ./examples
COPY README.md ./README.md

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY tests ./tests

ENTRYPOINT ["agentworkflow"]
CMD ["run", "--graph", "examples.research_workflow:build_graph", "--input", "{\"topic\": \"rust vs go\"}", "--trace"]
