# Development image for the API. Production image comes in Phase 7.
FROM python:3.12-slim

# Don't write .pyc files; flush logs immediately so `docker compose logs` is live.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only what's needed to install dependencies first, so Docker can cache this layer
# and skip reinstalling packages when only source files change.
COPY pyproject.toml ./
COPY app/__init__.py app/__init__.py
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000
