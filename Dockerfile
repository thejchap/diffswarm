# https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
FROM python:3.13-slim AS builder
ENV UV_COMPILE_BYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:0.8.8 /uv /uvx /bin/
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync --locked --no-install-project --no-editable --no-dev
COPY . /app
ARG GIT_HASH=dev
RUN echo $GIT_HASH > REVISION
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --no-editable
FROM python:3.13-slim
COPY --from=builder --chown=app:app /app/.venv /app/.venv
CMD ["/app/.venv/bin/diffswarm-server"]
