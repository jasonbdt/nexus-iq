FROM python:3.14.0-alpine
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

LABEL image.authors="Jason Bladt" \
      version="0.1.0"

WORKDIR /usr/src/app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

COPY app ./app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

CMD ["uv", "run", "rq", "worker"]
