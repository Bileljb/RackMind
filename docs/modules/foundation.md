# Foundation: how it works

- `docker compose up --build` starts 3 containers: `db` (Postgres), `redis`, `api`. The API waits for the other two to pass their healthchecks.
- On start, the API container runs `alembic upgrade head` (create/update tables), then `python -m app.seed` (demo data, skipped if already there), then `uvicorn --reload`. Your `api/` folder is mounted into the container, so saving a file restarts the server.
- Config comes from env vars, parsed and validated by `Settings` in `app/core/config.py`. A missing required var makes the app fail at startup instead of later.
- `app/core/db.py` creates one async engine (connection pool) per process and a session factory. `get_db` in `app/deps.py` opens one session per request and closes it after; endpoints receive it via `db: DbSession` (FastAPI dependency injection).
- Models live in `app/models/`, one file per table. All inherit from `Base`; `app/models/__init__.py` imports them all so Alembic sees every table.
- Schema changes: edit a model, then `docker compose exec api alembic revision --autogenerate -m "describe change"`, read the generated file in `alembic/versions/`, then `docker compose exec api alembic upgrade head`.
- Enums (role, severity, status) are stored as VARCHAR with a CHECK constraint, not Postgres ENUM types, so they are easy to change later.
- Tests: `docker compose exec api pytest`. Lint/types: `docker compose exec api ruff check .` and `docker compose exec api mypy`.
