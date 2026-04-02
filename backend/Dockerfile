FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY . .

EXPOSE 8000

CMD uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload \
    --reload-dir /app/core \
    --reload-dir /app/db \
    --reload-dir /app/eval \
    --reload-dir /app/evaluation \
    --reload-dir /app/excel \
    --reload-dir /app/infra \
    --reload-dir /app/pipeline \
    --reload-dir /app/prompts \
    --reload-dir /app/routers \
    --reload-dir /app/schemas \
    --reload-dir /app/skills \
    --reload-dir /app/tools
