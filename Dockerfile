FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY data ./data
COPY docs ./docs
COPY src ./src
COPY README.md ./

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "claims.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
