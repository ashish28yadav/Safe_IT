FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY main.py ./main.py
RUN pip install --no-cache-dir uv && uv sync --no-dev
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "incident_agent.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
