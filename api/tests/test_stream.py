"""Live events: Redis pub/sub in, Server-Sent Events out.

Uses the real Redis (pub/sub can't be faked meaningfully), on a channel of its own so
dashboards open during the test run don't receive test events.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
from arq import create_pool
from arq.connections import ArqRedis

from app.core.queue import redis_settings
from app.services.events import incident_event_stream

TEST_CHANNEL = "incidents-test"


@pytest.fixture
async def real_redis() -> AsyncIterator[ArqRedis]:
    redis = await create_pool(redis_settings())
    yield redis
    await redis.aclose()


async def test_published_events_reach_the_stream(real_redis: ArqRedis) -> None:
    stream = incident_event_stream(real_redis, channel=TEST_CHANNEL)
    first = asyncio.ensure_future(anext(stream))  # starts the subscription
    # Publish until the subscription is live (pub/sub drops messages sent before it).
    for _ in range(50):
        await real_redis.publish(TEST_CHANNEL, '{"action": "incident.opened"}')
        if first.done():
            break
        await asyncio.sleep(0.05)

    event = await asyncio.wait_for(first, timeout=2)
    await stream.aclose()

    assert event.event == "incident"
    assert event.raw_data == '{"action": "incident.opened"}'
