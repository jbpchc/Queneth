# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Install dependencies first so code edits don't bust the layer cache.
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py \
 && pip install ".[dev]" \
 && rm -rf app

FROM base AS dev
COPY . .
RUN pip install --no-deps -e .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
COPY . .
RUN pip install --no-deps .
RUN useradd --create-home queneth && mkdir -p /app/uploads && chown -R queneth /app/uploads
USER queneth
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
