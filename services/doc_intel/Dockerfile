# Build context: repository root (see docker-compose.yml).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY services ./services
RUN uv sync --frozen --no-dev --package doc-intel

EXPOSE 8003
CMD ["uvicorn", "doc_intel.main:app", "--host", "0.0.0.0", "--port", "8003"]
