"""Detection against the database: findings become incidents, deduplicated per server."""

from collections.abc import Awaitable, Callable
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Incident, IncidentStatus, Metric, Server, Severity
from app.services.detection import run_detection
from tests.conftest import FakeRedis
from tests.factories import ramp, series

Feed = Callable[[Server, list[Metric]], Awaitable[None]]


@pytest.fixture
def feed(db: AsyncSession, redis: FakeRedis) -> Feed:
    """`await feed(server, readings)`: store readings, then detect, like the worker per batch."""

    async def store_and_detect(server: Server, readings: list[Metric]) -> None:
        db.add_all(readings)
        await db.commit()
        await run_detection(db, redis, [server.id])  # type: ignore[arg-type]

    return store_and_detect


async def incidents_of(db: AsyncSession, server: Server) -> list[Incident]:
    stmt = select(Incident).where(Incident.server_id == server.id).order_by(Incident.id)
    return list(await db.scalars(stmt.execution_options(populate_existing=True)))


async def audit_actions(db: AsyncSession, incident: Incident) -> list[str]:
    stmt = select(AuditLog.action).where(AuditLog.entity_id == incident.id).order_by(AuditLog.id)
    return list(await db.scalars(stmt))


def split(readings: list[Metric], *minutes: float) -> list[list[Metric]]:
    """Cut a series into consecutive chunks ending at these minutes (5s readings)."""
    cuts = [int(m * 12) for m in minutes]
    return [readings[a:b] for a, b in zip([0, *cuts], [*cuts, len(readings)], strict=True)]


async def test_one_fault_opens_exactly_one_incident(
    db: AsyncSession, servers: list[Server], feed: Feed, redis: FakeRedis
) -> None:
    server = servers[0]
    # A disk at 80% starts filling at minute 25: warning soon, critical (>= 95%) by minute 30.
    readings = series(
        server.id, 31, fault=ramp("disk_used_pct", 3, start_min=25), base={"disk_used_pct": 80}
    )

    for chunk in split(readings, 24, 26, 27, 28, 29, 30):
        await feed(server, chunk)

    [incident] = await incidents_of(db, server)
    assert incident.metric_name == "disk_used_pct"
    assert incident.severity is Severity.CRITICAL
    assert incident.status is IncidentStatus.OPEN
    assert incident.title == f"High disk usage on {server.hostname}"
    actions = await audit_actions(db, incident)
    assert actions[0] == "incident.opened"
    assert set(actions[1:]) == {"incident.severity_raised"}
    # Live dashboards heard the same story, once per change.
    assert redis.actions() == actions
    assert redis.published[-1][1]["incident"]["severity"] == "critical"


async def test_normal_readings_open_nothing(
    db: AsyncSession, servers: list[Server], feed: Feed, redis: FakeRedis
) -> None:
    await feed(servers[0], series(servers[0].id, 30))

    assert await incidents_of(db, servers[0]) == []
    assert redis.published == []


async def test_recovery_is_suggested_then_withdrawn_if_the_fault_returns(
    db: AsyncSession, servers: list[Server], feed: Feed, redis: FakeRedis
) -> None:
    server = servers[0]

    def hot_spell(minute: float) -> dict[str, float]:
        """Critically hot (+40 C, so 85 C) during minutes 26-28, normal before and after."""
        return {"cpu_temp": 40} if 26 <= minute < 28 else {}

    readings = series(server.id, 30, fault=hot_spell)
    before, during, after = split(readings, 26, 28)

    await feed(server, before + during)
    [incident] = await incidents_of(db, server)
    assert incident.recovered_at is None

    await feed(server, after)
    [incident] = await incidents_of(db, server)
    assert incident.recovered_at == after[-1].timestamp
    assert incident.status is IncidentStatus.OPEN  # only a suggestion: still open

    # Hot again: the suggestion is withdrawn, and it is still the same single incident.
    next_minute = after[-1].timestamp + timedelta(minutes=1)
    await feed(server, series(server.id, 1, base={"cpu_temp": 85}, end=next_minute))
    [incident] = await incidents_of(db, server)
    assert incident.recovered_at is None
    assert redis.actions() == ["incident.opened", "incident.recovered", "incident.relapsed"]


async def test_a_resolved_incident_lets_a_new_fault_open_a_new_one(
    db: AsyncSession, servers: list[Server], feed: Feed
) -> None:
    server = servers[0]
    await feed(server, series(server.id, 1, base={"cpu_temp": 85}))
    [first] = await incidents_of(db, server)
    first.status = IncidentStatus.RESOLVED
    await db.commit()

    await feed(server, [])  # same hot readings, judged again

    assert [i.status for i in await incidents_of(db, server)] == [
        IncidentStatus.RESOLVED,
        IncidentStatus.OPEN,
    ]


async def test_each_server_gets_its_own_incident(
    db: AsyncSession, servers: list[Server], redis: FakeRedis
) -> None:
    for server in servers[:2]:
        db.add_all(series(server.id, 1, base={"cpu_temp": 85}))
    db.add_all(series(servers[2].id, 1))
    await db.commit()

    await run_detection(db, redis, [s.id for s in servers])  # type: ignore[arg-type]

    assert [len(await incidents_of(db, s)) for s in servers] == [1, 1, 0]


async def test_database_rejects_a_second_active_incident(
    db: AsyncSession, servers: list[Server]
) -> None:
    def incident() -> Incident:
        return Incident(
            server_id=servers[0].id, title="t", metric_name="cpu_temp", severity=Severity.INFO
        )

    db.add(incident())
    await db.commit()
    db.add(incident())

    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
