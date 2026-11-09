# One backend image, two entrypoints (api, worker) + migrate/seed/cli (ADR-0001, design D1).
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /bin/uv
# git: read-only repository connector (git archive / clone).
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN useradd -u 10001 -m archtwin
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
USER archtwin
# Fail the build if the tree-sitter grammar (compiled into the tree-sitter-python wheel) cannot load.
RUN python -c "from archtwin.connectors.analyzers.python_code import _parser; assert _parser().parse(b'x = 1').root_node.type == 'module'"
EXPOSE 8000
CMD ["uvicorn", "archtwin.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
