# Quaestor backend image — local-only (ADR-0026, supersedes 0010).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.21

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY alembic.ini ./alembic.ini

ENV PATH="/app/.venv/bin:${PATH}"

CMD ["python", "-m", "quaestor"]
