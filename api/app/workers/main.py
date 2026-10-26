"""ARQ worker process: runs background jobs that the API puts on the Redis queue.

Start it with `arq app.workers.main.WorkerSettings` (Docker Compose does this for you).
"""

from typing import Any

from arq.logs import default_log_config

from app.ai.client import llm_client_from_settings
from app.core import queue
from app.core.db import SessionFactory, engine
from app.models import Incident
from app.services.detection import run_detection
from app.services.diagnosis import run_diagnosis
from app.services.events import publish_incident_event

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
        # ctx["redis"] is the worker's own Redis connection, reused to publish live events.
        await run_detection(db, ctx["redis"], server_ids)


async def diagnose_incident(ctx: JobContext, incident_id: int) -> None:
    """Ask the LLM for a probable cause, store the result (or why it failed), tell browsers.

    Queued when the detector opens an incident, or when an engineer asks for a new attempt.
    """
    async with SessionFactory() as db:
        await run_diagnosis(db, incident_id, ctx["llm"])
        incident = await db.get_one(Incident, incident_id)
        await publish_incident_event(ctx["redis"], "incident.diagnosed", incident)


async def startup(ctx: JobContext) -> None:
    # One API client for the worker's lifetime: it keeps HTTP connections open between jobs.
    ctx["llm"] = llm_client_from_settings()


async def shutdown(ctx: JobContext) -> None:
    if ctx.get("llm") is not None:
        await ctx["llm"].close()
    # Close the DB connection pool cleanly when the worker stops.
    await engine.dispose()


class WorkerSettings:
    """Read by the `arq` command: which jobs exist, where Redis is, and lifecycle hooks."""

    functions = [detect_anomalies, diagnose_incident]
    redis_settings = queue.redis_settings()
    on_startup = startup
    on_shutdown = shutdown
