import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.add_server import HostnameTakenError, add_server
from app.models import Rack, Server, ServerSource


async def test_creates_the_group_then_fills_its_next_slots(db: AsyncSession) -> None:
    first = await add_server(db, "web-01", "Production")
    second = await add_server(db, "db-01", "Production")

    rack = await db.get_one(Rack, first.rack_id)
    assert rack.name == "Production"
    assert second.rack_id == rack.id
    assert (first.rack_unit, second.rack_unit) == (1, 2)
    assert first.source is ServerSource.AGENT


async def test_joins_an_existing_group(db: AsyncSession, servers: list[Server]) -> None:
    server = await add_server(db, "web-01", "R01")  # R01 holds two simulated servers

    assert server.rack_id == servers[0].rack_id
    assert server.rack_unit == 3


async def test_rejects_a_taken_hostname(db: AsyncSession, servers: list[Server]) -> None:
    with pytest.raises(HostnameTakenError):
        await add_server(db, servers[0].hostname, "Production")
