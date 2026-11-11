"""Simulation mode: browsers keep a lease alive in Redis, the simulator reads it."""

from collections.abc import Callable

import pytest
from httpx import AsyncClient

from app.models import Role, User
from app.services.simulation import ACTIVE_KEY, LEASE_S
from tests.conftest import INGEST_HEADERS, FakeRedis


@pytest.fixture(autouse=True)
def logged_in(login: Callable[[Role], User]) -> None:
    login(Role.OPERATOR)  # even the lowest role may explore the demo


async def active(client: AsyncClient) -> bool:
    response = await client.get("/simulation/status")
    assert response.status_code == 200
    return bool(response.json()["active"])


async def test_inactive_until_someone_enters_simulation_mode(client: AsyncClient) -> None:
    assert await active(client) is False


async def test_keepalive_starts_it_with_an_expiring_lease(
    client: AsyncClient, redis: FakeRedis
) -> None:
    response = await client.post("/simulation/keepalive")

    assert response.status_code == 204
    assert await active(client) is True
    # The lease expires on its own if the browser stops refreshing (tab closed, offline).
    assert redis.expiry_s[ACTIVE_KEY] == LEASE_S


async def test_switching_back_to_live_stops_it_at_once(client: AsyncClient) -> None:
    await client.post("/simulation/keepalive")

    response = await client.delete("/simulation/keepalive")

    assert response.status_code == 204
    assert await active(client) is False


async def test_the_simulator_reads_the_status_with_its_key(
    client: AsyncClient, redis: FakeRedis
) -> None:
    await client.post("/simulation/keepalive")
    client.cookies.clear()
    client.headers.update(INGEST_HEADERS)

    assert await active(client) is True
