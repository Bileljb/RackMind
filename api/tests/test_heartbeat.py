"""Heartbeat: a real server that goes silent gets one "not reporting" incident."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue import DIAGNOSE_JOB
from app.models import Incident, IncidentStatus, Server, ServerSource, Severity
from app.services.detection import run_detection
from app.services.heartbeat import run_heartbeat, silence_finding
from tests.conftest import FakeRedis
from tests.factories import series

TIMEOUT = timedelta(seconds=60)
NOW = datetime.now(UTC)


@pytest.fixture
async def agent(db: AsyncSession, servers: list[Server]) -> Server:
    """A real server that sent readings until 2 minutes ago."""
    server = servers[0]
    server.source = ServerSource.AGENT
    db.add_all(series(server.id, 5, end=NOW - timedelta(minutes=2)))
    await db.commit()
    return server


async def incidents_of(db: AsyncSession, server: Server) -> list[Incident]:
    stmt = select(Incident).where(Incident.server_id == server.id).order_by(Incident.id)
    return list(await db.scalars(stmt.execution_options(populate_existing=True)))


@pytest.mark.parametrize(
    ("silent_for", "expected"),
    [(timedelta(seconds=60), None), (timedelta(seconds=61), Severity.CRITICAL)],
)
def test_silence_limit(silent_for: timedelta, expected: Severity | None) -> None:
    finding = silence_finding(NOW - silent_for, NOW, TIMEOUT)

    assert (finding.severity if finding else None) == expected


async def test_silent_agent_opens_one_critical_incident(
    db: AsyncSession, agent: Server, redis: FakeRedis
) -> None:
    await run_heartbeat(db, redis, NOW, TIMEOUT)  # type: ignore[arg-type]
    next_tick = NOW + timedelta(seconds=30)
    await run_heartbeat(db, redis, next_tick, TIMEOUT)  # type: ignore[arg-type]

    [incident] = await incidents_of(db, agent)
    assert incident.title == f"{agent.hostname} is not reporting"
    assert incident.metric_name == "heartbeat"
    assert incident.severity is Severity.CRITICAL
    assert redis.actions() == ["incident.opened"]  # the second tick changed nothing
    assert (DIAGNOSE_JOB, (incident.id,)) in redis.jobs


async def test_readings_coming_back_suggest_recovery(
    db: AsyncSession, agent: Server, redis: FakeRedis
) -> None:
    await run_heartbeat(db, redis, NOW, TIMEOUT)  # type: ignore[arg-type]

    db.add_all(series(agent.id, 0.5, end=datetime.now(UTC)))
    await db.commit()
    await run_detection(db, redis, [agent.id])  # type: ignore[arg-type]

    [incident] = await incidents_of(db, agent)
    assert incident.recovered_at is not None
    assert incident.status is IncidentStatus.OPEN  # a person still decides to resolve it


async def test_existing_incident_is_escalated_not_duplicated(
    db: AsyncSession, agent: Server, redis: FakeRedis
) -> None:
    db.add(
        Incident(
            server_id=agent.id,
            title="High memory",
            metric_name="memory_used_pct",
            severity=Severity.WARNING,
        )
    )
    await db.commit()

    await run_heartbeat(db, redis, NOW, TIMEOUT)  # type: ignore[arg-type]

    [incident] = await incidents_of(db, agent)
    assert incident.severity is Severity.CRITICAL
    assert redis.actions() == ["incident.severity_raised"]


async def test_simulated_and_never_connected_servers_are_ignored(
    db: AsyncSession, servers: list[Server], redis: FakeRedis
) -> None:
    simulated, never_connected, _ = servers
    db.add_all(series(simulated.id, 5, end=NOW - timedelta(minutes=10)))  # paused simulation
    never_connected.source = ServerSource.AGENT  # registered, agent not started yet
    await db.commit()

    await run_heartbeat(db, redis, NOW, TIMEOUT)  # type: ignore[arg-type]

    assert redis.published == []
