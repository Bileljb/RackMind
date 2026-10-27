# Same layout as api/Dockerfile: a `dev` target with test tools, a slim `prod` target.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY rackmind_sim/__init__.py rackmind_sim/__init__.py


FROM base AS dev
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
CMD ["python", "-m", "rackmind_sim"]


FROM base AS prod
RUN pip install --no-cache-dir -e . && useradd --create-home rackmind
COPY . .
USER rackmind
CMD ["python", "-m", "rackmind_sim"]
