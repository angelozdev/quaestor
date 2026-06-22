# Quaestor backend image — multi-stage (ADR-0013).
# `prod` (default) is what production (P7) uses.
# `dev` is what the local dev override (docker-compose.override.yml) builds.

# --- dev stage: includes dev deps so uvicorn --reload works.
FROM python:3.12-slim AS dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.21

COPY pyproject.toml uv.lock ./
# Sync WITH dev deps (pytest, watchfiles).
RUN uv sync --frozen

COPY src/ ./src/
COPY scripts/ ./scripts/
RUN chmod +x ./scripts/cron.sh

ENV PATH="/app/.venv/bin:${PATH}"

# --- prod stage: drops dev deps. Default target for production builds.
FROM dev AS prod

RUN uv sync --frozen --no-dev

CMD ["uv", "run", "uvicorn", "quaestor.api:app", "--host", "0.0.0.0", "--port", "8000"]