from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.models import Server
from tests.conftest import reading


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def test_list_racks(client: AsyncClient, servers: list[Server]) -> None:
    response = await client.get("/racks")

    assert response.status_code == 200
    assert [rack["name"] for rack in response.json()] == ["R01", "R02"]


async def test_list_servers_all_and_by_rack(client: AsyncClient, servers: list[Server]) -> None:
    every = (await client.get("/servers")).json()
    in_rack = (await client.get("/servers", params={"rack_id": servers[0].rack_id})).json()

    assert [s["hostname"] for s in every] == ["r01-srv01", "r01-srv02", "r02-srv01"]
    assert [s["hostname"] for s in in_rack] == ["r01-srv01", "r01-srv02"]


async def test_get_server(client: AsyncClient, servers: list[Server]) -> None:
    found = await client.get(f"/servers/{servers[0].id}")
    missing = await client.get("/servers/9999")

    assert found.status_code == 200
    assert found.json()["hostname"] == "r01-srv01"
    assert missing.status_code == 404


async def test_latest_returns_newest_reading_per_server(
    client: AsyncClient, servers: list[Server]
) -> None:
    now = datetime.now(UTC)
    first, second, _no_readings = servers
    batch = [
        reading(first.id, now - timedelta(minutes=2), cpu_temp=40),
        reading(first.id, now, cpu_temp=60),
        reading(first.id, now - timedelta(minutes=1), cpu_temp=50),
        reading(second.id, now - timedelta(minutes=5), cpu_temp=42),
    ]
    await client.post("/metrics/batch", json=batch)

    response = await client.get("/metrics/latest")

    assert response.status_code == 200
    latest = {row["server_id"]: row["cpu_temp"] for row in response.json()}
    assert latest == {first.id: 60, second.id: 42}  # third server has no readings: left out


async def test_latest_filters_by_rack(client: AsyncClient, servers: list[Server]) -> None:
    await client.post("/metrics/batch", json=[reading(s.id) for s in servers])

    response = await client.get("/metrics/latest", params={"rack_id": servers[2].rack_id})

    assert [row["server_id"] for row in response.json()] == [servers[2].id]


async def test_history_defaults_to_last_hour_oldest_first(
    client: AsyncClient, servers: list[Server]
) -> None:
    now = datetime.now(UTC)
    server = servers[0]
    times = [now - timedelta(minutes=m) for m in (90, 30, 1, 10)]
    await client.post("/metrics/batch", json=[reading(server.id, t) for t in times])

    response = await client.get(f"/servers/{server.id}/metrics")

    assert response.status_code == 200
    returned = [parse_time(row["timestamp"]) for row in response.json()]
    assert returned == sorted(times[1:])  # the 90-minute-old reading is outside the window


async def test_history_respects_explicit_range(client: AsyncClient, servers: list[Server]) -> None:
    start = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    server = servers[0]
    times = [start - timedelta(minutes=1), start, start + timedelta(minutes=5)]
    await client.post("/metrics/batch", json=[reading(server.id, t) for t in times])
    await client.post("/metrics", json=reading(servers[1].id, start))  # other server: ignored

    params = {"start": start.isoformat(), "end": (start + timedelta(minutes=5)).isoformat()}
    response = await client.get(f"/servers/{server.id}/metrics", params=params)

    # start is included, end is excluded: [start, end)
    assert [parse_time(row["timestamp"]) for row in response.json()] == [start]


async def test_history_rejects_bad_ranges(client: AsyncClient, servers: list[Server]) -> None:
    now = datetime.now(UTC)
    url = f"/servers/{servers[0].id}/metrics"

    backwards = {"start": now.isoformat(), "end": (now - timedelta(minutes=1)).isoformat()}
    too_long = {"start": (now - timedelta(hours=25)).isoformat(), "end": now.isoformat()}
    naive = {"start": "2026-10-25T10:00:00"}

    for params in (backwards, too_long, naive):
        assert (await client.get(url, params=params)).status_code == 422


async def test_history_unknown_server_is_404(client: AsyncClient, servers: list[Server]) -> None:
    response = await client.get("/servers/9999/metrics")

    assert response.status_code == 404
