"""Live incident events: published on Redis pub/sub, streamed to browsers over SSE.

Pub/sub is a broadcast: every subscriber connected *right now* gets each message, nobody
stores it. The API and the worker publish after their DB commit; each open `/stream`
connection subscribes and forwards what it hears to its browser.
"""

import logging
from collections.abc import AsyncGenerator

from arq.connections import ArqRedis
from fastapi.sse import ServerSentEvent
from redis.exceptions import RedisError

from app.models import Incident
from app.schemas.incident import IncidentEvent, IncidentOut

logger = logging.getLogger(__name__)

CHANNEL = "incidents"


async def publish_incident_event(redis: ArqRedis, action: str, incident: Incident) -> None:
    """Tell live dashboards that `incident` changed. Best effort: the DB is the source of truth.

    If Redis is down the change is still saved; screens catch up on their next reload.
    """
    event = IncidentEvent(action=action, incident=IncidentOut.model_validate(incident))
    try:
        await redis.publish(CHANNEL, event.model_dump_json())
    except RedisError:
        logger.warning("Could not publish %s for incident %s", action, incident.id, exc_info=True)


async def incident_event_stream(
    redis: ArqRedis, channel: str = CHANNEL
) -> AsyncGenerator[ServerSentEvent]:
    """Forever: wait for the next published event and turn it into an SSE message.

    Each caller gets its own subscription (one Redis connection), closed when the browser
    disconnects and FastAPI stops this generator.
    """
    async with redis.pubsub() as pubsub:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":  # skip the "subscribed" confirmation
                yield ServerSentEvent(event="incident", raw_data=message["data"].decode())
