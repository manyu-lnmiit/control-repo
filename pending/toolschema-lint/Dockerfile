FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

COPY tests ./tests

ENTRYPOINT ["toolschema-lint"]
CMD ["--help"]
