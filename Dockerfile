# https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.8 /uv /uvx /bin/
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN --mount=type=secret,id=SAPLING_TOKEN \
  --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  git config --global url."https://x-access-token:$(cat /run/secrets/SAPLING_TOKEN)@github.com/".insteadOf "https://github.com/" && \
  uv sync --locked --no-install-project --no-dev
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked
CMD ["/app/.venv/bin/diffswarm-server"]
