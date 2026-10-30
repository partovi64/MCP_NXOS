# Non-root, slim production image for nxos-mcp (stdio transport).
# Copy inventory/guardrails/redaction config and set NXOS_* env vars at run time.
FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python --no-cache .

FROM python:3.12-slim

# Non-root user
RUN groupadd -r nxos && useradd -r -g nxos -d /app -s /usr/sbin/nologin nxos
COPY --from=build --chown=nxos:nxos /opt/venv /opt/venv

USER nxos
WORKDIR /app
ENV PATH=/opt/venv/bin:$PATH \
    NXOS_INVENTORY=/app/config/inventory.yaml \
    NXOS_GUARDRAILS=/app/config/guardrails.yaml \
    NXOS_REDACTION=/app/config/redaction.yaml

# Config is mounted read-only at runtime: -v $PWD/config:/app/config:ro
VOLUME ["/app/config"]

# stdio transport by default; override env for streamable-http
ENTRYPOINT ["nxos-mcp"]
