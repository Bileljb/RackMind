"""ARQ worker process: runs background jobs that the API puts on the Redis queue.

Start it with `arq app.workers.main.WorkerSettings` (Docker Compose does this for you).
"""

from typing import Any

from arq.logs import default_log_config

from app.core import queue
from app.core.db import SessionFactory, engine
from app.services.detection import run_detection

# ARQ's own log setup only covers its `arq.*` loggers. This adds ours (`app.*`) on the same
# handler; Compose passes it with `--custom-log-dict app.workers.main.LOG_CONFIG`.
LOG_CONFIG = default_log_config(verbose=False)
LOG_CONFIG["loggers"]["app"] = {"handlers": ["arq.standard"], "level": "INFO"}

# ARQ passes every job a `ctx` dict as its first argument. It holds the Redis connection, job
# metadata (job_id, job_try), and anything `on_startup` adds to it.
JobContext = dict[str, Any]


async def detect_anomalies(ctx: JobContext, server_ids: list[int]) -> None:
    """Check these servers' newest readings; open, escalate or mark incidents as recovered.

    Queued by the API after every metrics batch (see `request_detection`).
    """
    async with SessionFactory() as db:
        await run_detection(db, server_ids)


async def shutdown(ctx: JobContext) -> None:
    # Close the DB connection pool cleanly when the worker stops.
    await engine.dispose()


class WorkerSettings:
    """Read by the `arq` command: which jobs exist, where Redis is, and lifecycle hooks."""

    functions = [detect_anomalies]
    redis_settings = queue.redis_settings()
    on_shutdown = shutdown
