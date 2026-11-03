FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    HOME=/home/incident-agent \
    APP_ENV=production \
    INCIDENT_AGENT_DATABASE_URL=sqlite:////app/data/incidents.db

RUN groupadd --system --gid 10001 incident-agent \
    && useradd --system --uid 10001 --gid incident-agent --create-home --home-dir /home/incident-agent incident-agent

WORKDIR /app

COPY --chown=10001:10001 pyproject.toml uv.lock ./
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 knowledge_base ./knowledge_base
COPY --chown=10001:10001 alembic.ini ./alembic.ini
COPY --chown=10001:10001 alembic ./alembic
COPY --chown=10001:10001 main.py ./main.py

RUN pip install --no-cache-dir uv \
    && uv sync --no-dev \
    && mkdir -p /app/data \
    && chown 10001:10001 /app/data

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request; [urllib.request.urlopen(url, timeout=3) for url in ('http://127.0.0.1:8000/health', 'http://127.0.0.1:8000/api/v1/retrieval/health')]"]

CMD ["/app/.venv/bin/uvicorn", "incident_agent.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]
