FROM node:24-alpine AS web-builder

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 versionweaver \
    && mkdir /data \
    && chown versionweaver:versionweaver /data
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
ENV VERSIONWEAVER_DATABASE_URL="sqlite:////data/versionweaver.sqlite3"
ENV VERSIONWEAVER_ARTIFACT_DIR="/data/artifacts"
ENV VERSIONWEAVER_WEB_DIST_DIR="/app/web"
COPY --from=builder /app/.venv /app/.venv
COPY --from=web-builder /web/dist /app/web
COPY alembic.ini ./
COPY migrations ./migrations
USER versionweaver
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "versionweaver.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
