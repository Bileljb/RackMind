from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Metric, Server
from app.routers.metrics import MAX_BATCH_SIZE
from tests.conftest import reading


async def count_metrics(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(Metric)) or 0


async def test_ingest_one_stores_and_returns_reading(
    client: AsyncClient, db: AsyncSession, servers: list[Server]
) -> None:
    response = await client.post("/metrics", json=reading(servers[0].id, cpu_temp=51.5))

    assert response.status_code == 201
    body = response.json()
    assert body["server_id"] == servers[0].id
    assert body["cpu_temp"] == 51.5
    assert isinstance(body["id"], int)
    assert await count_metrics(db) == 1


async def test_ingest_batch_stores_all_readings(
    client: AsyncClient, db: AsyncSession, servers: list[Server]
) -> None:
    response = await client.post("/metrics/batch", json=[reading(s.id) for s in servers])

    assert response.status_code == 201
    assert response.json() == {"inserted": len(servers)}
    assert await count_metrics(db) == len(servers)


@pytest.mark.parametrize(
    "overrides",
    [
        {"disk_used_pct": 100.1},
        {"memory_used_pct": -1},
        {"power_w": -5},
        {"network_mbps": -0.1},
        {"cpu_temp": 200},
        {"cpu_temp": "hot"},
        {"timestamp": "2026-10-25T10:00:00"},  # no timezone
        {"timestamp": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
        {"server_id": 0},
    ],
)
async def test_ingest_rejects_invalid_values(
    client: AsyncClient, db: AsyncSession, servers: list[Server], overrides: dict[str, object]
) -> None:
    response = await client.post("/metrics", json={**reading(servers[0].id), **overrides})

    assert response.status_code == 422
    assert await count_metrics(db) == 0


async def test_ingest_rejects_missing_field(client: AsyncClient, servers: list[Server]) -> None:
    payload = reading(servers[0].id)
    del payload["power_w"]

    response = await client.post("/metrics", json=payload)

    assert response.status_code == 422


async def test_ingest_rejects_unknown_server(client: AsyncClient, servers: list[Server]) -> None:
    response = await client.post("/metrics", json=reading(9999))

    assert response.status_code == 422
    assert response.json()["detail"]["server_ids"] == [9999]


async def test_batch_with_one_unknown_server_inserts_nothing(
    client: AsyncClient, db: AsyncSession, servers: list[Server]
) -> None:
    response = await client.post("/metrics/batch", json=[reading(servers[0].id), reading(9999)])

    assert response.status_code == 422
    assert await count_metrics(db) == 0


async def test_batch_with_one_invalid_reading_inserts_nothing(
    client: AsyncClient, db: AsyncSession, servers: list[Server]
) -> None:
    batch = [reading(servers[0].id), reading(servers[1].id, disk_used_pct=150)]

    response = await client.post("/metrics/batch", json=batch)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", 1, "disk_used_pct"]
    assert await count_metrics(db) == 0


@pytest.mark.parametrize("size", [0, MAX_BATCH_SIZE + 1])
async def test_batch_size_limits(client: AsyncClient, servers: list[Server], size: int) -> None:
    response = await client.post("/metrics/batch", json=[reading(servers[0].id)] * size)

    assert response.status_code == 422
