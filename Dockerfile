FROM ghcr.io/astral-sh/uv:0.11.31 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend ./backend
COPY shared ./shared
CMD ["sh", "-c", "uv run --no-sync uvicorn backend.app.main:app --host 0.0.0.0 --port \"${PORT:?PORT is required}\""]
