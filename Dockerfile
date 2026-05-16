FROM python:3.13.0-alpine3.20
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

LABEL image.authors="Jason Bladt" \
      version="1.0.0"

WORKDIR /usr/src

RUN addgroup -S app && adduser -S app -G app \
    && apk add --no-cache su-exec

COPY docker-entrypoint-backend.sh /docker-entrypoint-backend.sh
RUN chmod +x /docker-entrypoint-backend.sh

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

COPY ./app app/

ENV UV_NO_DEV=1

RUN --mount=type=cache,target=/root/.cache/uv \
    mkdir -p /usr/src/ddragon/cdn \
    && uv sync --dev --locked \
    && chown -R app:app /usr/src/app /usr/src/ddragon

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint-backend.sh"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/usr/src/app"]
