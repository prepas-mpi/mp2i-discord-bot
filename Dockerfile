FROM pypy:3.11-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.8.21 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

########################################################################

FROM pypy:3.11-slim AS runtime

RUN apt-get update && apt-get install -y libpq-dev

ENV PATH="/app/.venv/bin:$PATH"

ARG GID
ARG UID

RUN groupadd -g ${GID} app-bot && \
    useradd -u ${UID} -g app-bot -m -d /app -s /bin/false app-bot

WORKDIR /app

COPY --from=build --chown=app-bot:app-bot /app .

USER app-bot

ENTRYPOINT ["python", "-m", "mp2i"]
