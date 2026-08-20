# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source and install the package itself.
COPY src ./src
COPY examples ./examples
COPY README.md LICENSE ./
RUN pip install --no-cache-dir .

# Default command runs the example, which exercises the full pipeline and
# doubles as a smoke test in CI.
CMD ["python", "examples/basic_usage.py"]
