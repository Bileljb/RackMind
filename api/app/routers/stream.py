from collections.abc import AsyncIterable

from fastapi import APIRouter
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.deps import DbSession, Operator, Redis
from app.services.events import incident_event_stream

router = APIRouter(tags=["stream"])


@router.get("/stream", response_class=EventSourceResponse)
async def stream(db: DbSession, redis: Redis, _: Operator) -> AsyncIterable[ServerSentEvent]:
    """Live incident events for any logged-in user, as Server-Sent Events.

    The response never ends on its own: each `yield` sends one event down the open HTTP
    connection. FastAPI also sends a `: ping` comment every 15s so proxies keep it open.
    """
    # Login was checked (by `Operator`). Hand the DB connection back to the pool now: this
    # request can stay open for hours and must not hold a connection the whole time.
    await db.close()
    async for event in incident_event_stream(redis):
        yield event
