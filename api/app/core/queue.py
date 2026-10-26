"""The ARQ job queue on Redis: the API adds jobs to it, the worker runs them."""

import logging
from collections.abc import Iterable

from arq.connections import ArqRedis, RedisSettings
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Jobs are referred to by the name of the worker function that runs them.
DETECT_JOB = "detect_anomalies"
DIAGNOSE_JOB = "diagnose_incident"


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(str(get_settings().redis_url))


async def request_detection(queue: ArqRedis, server_ids: Iterable[int]) -> None:
    """Ask the worker to check these servers' newest readings.

    Best effort: if Redis is down, the readings are already saved, so we log and move on rather
    than fail the request. The next batch (5s later) triggers detection again anyway.
    """
    ids = sorted(set(server_ids))
    try:
        await queue.enqueue_job(DETECT_JOB, ids)
    except RedisError:
        logger.warning("Could not queue detection for servers %s", ids, exc_info=True)
