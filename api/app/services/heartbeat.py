"""Heartbeat: notices real servers that stopped sending readings.

Detection runs when readings *arrive*, so on its own it can never notice a server that went
silent: no readings, no check. This job runs on a timer instead (every 30s, see the worker)
and treats silence itself as a finding. It then goes through the same incident rules as
detection: one active incident per server, escalate rather than duplicate, and when readings
come back detection marks the incident "looks recovered" (a person still resolves it).

Only `agent` servers are checked: simulated ones are silent on purpose while nobody is in
Simulation mode.
"""

from datetime import datetime, timedelta

from arq.connections import ArqRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Server, ServerSource, Severity
from app.services import metrics as metrics_service
from app.services.detection import (
    HEARTBEAT_METRIC,
    Change,
    active_incidents,
    apply_findings,
    publish_changes,
)
from app.services.detector import Finding


def silence_finding(last_seen: datetime, now: datetime, limit: timedelta) -> Finding | None:
    """A critical finding if the newest reading is older than `limit`, else None.

    Critical on purpose: a server that can't report may be down, and every other check
    is blind for as long as it stays silent.
    """
    silent_for = now - last_seen
    if silent_for <= limit:
        return None
    seconds = silent_for.total_seconds()
    return Finding(
        metric=HEARTBEAT_METRIC,
        severity=Severity.CRITICAL,
        value=seconds,
        reason=f"no readings for {seconds:.0f}s (limit {limit.total_seconds():.0f}s)",
    )


async def run_heartbeat(db: AsyncSession, redis: ArqRedis, now: datetime, limit: timedelta) -> None:
    """Open or escalate an incident for every silent agent server, in one transaction.

    Servers that never sent a reading are skipped: they were registered but not connected
    yet, which is not an outage.
    """
    latest = await metrics_service.latest_metrics(db, source=ServerSource.AGENT)
    silent = {
        reading.server_id: finding
        for reading in latest
        if (finding := silence_finding(reading.timestamp, now, limit)) is not None
    }
    if not silent:
        return
    servers = await db.scalars(select(Server).where(Server.id.in_(list(silent))))
    active = await active_incidents(db, list(silent))

    changes: list[Change] = []
    for server in servers:
        finding = silent[server.id]
        change = await apply_findings(db, server, active.get(server.id), [finding], now)
        if change is not None:
            changes.append(change)
    await db.commit()
    await publish_changes(redis, changes)
