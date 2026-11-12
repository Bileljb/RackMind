# One image for Render's free plan, which has web services but no background workers:
# the API, the ARQ worker and the simulator all run in this container (see start.sh).
# Build context is the repo root: `docker build -f deploy/render/Dockerfile .`
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencies first, so this layer is cached when only source files change.
COPY api/pyproject.toml /app/api/pyproject.toml
COPY api/app/__init__.py /app/api/app/__init__.py
COPY simulator/pyproject.toml /app/simulator/pyproject.toml
COPY simulator/rackmind_sim/__init__.py /app/simulator/rackmind_sim/__init__.py
RUN pip install --no-cache-dir -e /app/api -e /app/simulator && useradd --create-home rackmind

COPY api /app/api
COPY simulator /app/simulator
COPY deploy/render/start.sh /app/start.sh

USER rackmind
WORKDIR /app/api
CMD ["sh", "/app/start.sh"]
