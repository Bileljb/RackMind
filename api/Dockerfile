# Two targets share one base: `dev` (docker-compose.yml) and `prod` (docker-compose.prod.yml).
# Build one with `docker build --target dev ./api`.
FROM python:3.12-slim AS base

# Don't write .pyc files; flush logs immediately so `docker compose logs` is live.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only what's needed to install dependencies first, so Docker can cache this layer
# and skip reinstalling packages when only source files change.
COPY pyproject.toml ./
COPY app/__init__.py app/__init__.py


# ---------- dev: test/lint tools included, source mounted by Compose ----------
FROM base AS dev
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
EXPOSE 8000


# ---------- prod: runtime dependencies only, runs as a non-root user ----------
FROM base AS prod
RUN pip install --no-cache-dir -e . && useradd --create-home rackmind
COPY . .
USER rackmind
EXPOSE 8000
# Apply migrations, seed demo data (skipped if present), then serve without --reload.
# --proxy-headers: trust X-Forwarded-* from the reverse proxy (Caddy) in front of the app.
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
