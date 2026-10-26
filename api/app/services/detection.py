"""Runs the detector on fresh readings and turns its findings into incidents.

Deduplication: a server has at most one active (not resolved) incident. While it is active,
new findings on that server only raise its severity; they never open a second incident.
"""

import logging
from collections.abc import Collection
from datetime import UTC, datetime

from arq.connections import ArqRedis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident, IncidentStatus, Server
from app.services import detector
from app.services import diagnosis as diagnosis_service
from app.services import metrics as metrics_service
from app.services.audit import record_incident_event
from app.services.detector import Finding
from app.services.events import publish_incident_event

logger = logging.getLogger(__name__)

METRIC_LABELS = {
    "cpu_temp": "CPU temperature",
    "power_w": "power draw",
    "disk_used_pct": "disk usage",
    "memory_used_pct": "memory usage",
    "network_mbps": "network traffic",
}

# What changed on an incident, to tell live dashboards: (event action, incident).
Change = tuple[str, Incident]


async def run_detection(db: AsyncSession, redis: ArqRedis, server_ids: Collection[int]) -> None:
    """Evaluate each server's recent readings and update its incident, in one transaction.

    Live events are published only after the commit, so a browser that reacts to one by
    fetching the incident is guaranteed to find it.
    """
    since = datetime.now(UTC) - detector.LOOKBACK
    readings = await metrics_service.recent_readings(db, server_ids, since)
    servers = await db.scalars(select(Server).where(Server.id.in_(list(readings))))
    active = await _active_incidents(db, list(readings))

    changes: list[Change] = []
    for server in servers:
        server_readings = readings[server.id]
        findings = detector.evaluate(server_readings)
        checked_at = server_readings[-1].timestamp
        change = await _apply_findings(db, server, active.get(server.id), findings, checked_at)
        if change is not None:
            changes.append(change)
    await db.commit()

    for action, incident in changes:
        await publish_incident_event(redis, action, incident)
        if action == "incident.opened":
            await diagnosis_service.enqueue(redis, incident.id)  # ask the AI for a cause


async def _active_incidents(db: AsyncSession, server_ids: Collection[int]) -> dict[int, Incident]:
    stmt = select(Incident).where(
        Incident.server_id.in_(server_ids), Incident.status != IncidentStatus.RESOLVED
    )
    return {incident.server_id: incident for incident in await db.scalars(stmt)}


async def _apply_findings(
    db: AsyncSession,
    server: Server,
    incident: Incident | None,
    findings: list[Finding],
    checked_at: datetime,
) -> Change | None:
    if not findings:
        if incident is not None and incident.recovered_at is None:
            incident.recovered_at = checked_at  # suggest resolving; a person decides
            return "incident.recovered", incident
        return None

    worst = max(findings, key=lambda finding: finding.severity.rank)
    if incident is None:
        opened = await _open_incident(db, server, worst, findings)
        return ("incident.opened", opened) if opened else None

    change: Change | None = None
    if incident.recovered_at is not None:
        incident.recovered_at = None  # the anomaly is back: withdraw the suggestion
        change = "incident.relapsed", incident
    if worst.severity.rank > incident.severity.rank:
        record_incident_event(
            db,
            incident.id,
            "incident.severity_raised",
            actor=None,
            previous=incident.severity,
            severity=worst.severity,
            metric=worst.metric,
            reason=worst.reason,
        )
        incident.severity = worst.severity
        change = "incident.severity_raised", incident
    return change


async def _open_incident(
    db: AsyncSession, server: Server, worst: Finding, findings: list[Finding]
) -> Incident | None:
    # ON CONFLICT DO NOTHING: if another job opened an incident for this server a moment ago,
    # the unique index `uq_incidents_active_server` rejects this row and we get nothing back,
    # instead of an error. That job's incident is the one; nothing else to do.
    stmt = (
        insert(Incident)
        .values(
            server_id=server.id,
            title=f"High {METRIC_LABELS[worst.metric]} on {server.hostname}",
            metric_name=worst.metric,
            severity=worst.severity,
        )
        .on_conflict_do_nothing()
        .returning(Incident)
    )
    incident = await db.scalar(stmt)
    if incident is None:
        return None
    record_incident_event(
        db,
        incident.id,
        "incident.opened",
        actor=None,
        severity=worst.severity,
        findings=[
            {
                "metric": f.metric,
                "severity": f.severity,
                "value": round(f.value, 2),
                "reason": f.reason,
            }
            for f in findings
        ],
    )
    diagnosis_service.add_pending(db, incident.id)
    logger.info("Opened incident %s (%s) on %s", incident.id, worst.severity, server.hostname)
    return incident
