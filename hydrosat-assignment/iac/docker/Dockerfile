ARG PYTHON_IMAGE=python:3.11.13-slim
ARG UV_VERSION=0.9.13
ARG VENV_PATH=/opt/.venv

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM ${PYTHON_IMAGE} AS builder

ARG VENV_PATH
ENV PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=${VENV_PATH} \
    PATH="${VENV_PATH}/bin:$PATH"

WORKDIR /app

RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential gdal-bin libgdal-dev && \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/
COPY pyproject.toml uv.lock .python-version ./

RUN uv venv ${VENV_PATH} && \
    . ${VENV_PATH}/bin/activate && \
    uv sync --locked --no-editable --active

COPY ./src/ ./src

FROM ${PYTHON_IMAGE}

ARG VENV_PATH
ENV PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=${VENV_PATH} \
    PATH="${VENV_PATH}/bin:$PATH"

WORKDIR /app

RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev && \
    rm -rf /var/lib/apt/lists/* && \
    gdalinfo --version

COPY --from=builder ${VENV_PATH} ${VENV_PATH}
COPY --from=builder /app/src/ ./src

EXPOSE 3000

CMD ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000"]
