FROM python:3.11-slim

# unshare (from util-linux) enables best-effort network namespace isolation
# for sandboxed executions. It is optional -- the package falls back
# gracefully if it's missing or unprivileged -- but we install it here so
# the image demonstrates the full feature set.
RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

# Run as a non-root user so subprocess rlimits/permissions reflect a
# realistic deployment rather than root (which can bypass some limits).
RUN useradd --create-home --uid 1000 sandbox
USER sandbox

ENTRYPOINT ["agent-code-sandbox"]
CMD ["run-python", "print('agent-code-sandbox is ready')"]
