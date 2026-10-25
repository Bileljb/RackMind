# Development image for the simulator (same layout as api/Dockerfile).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY rackmind_sim/__init__.py rackmind_sim/__init__.py
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

CMD ["python", "-m", "rackmind_sim"]
