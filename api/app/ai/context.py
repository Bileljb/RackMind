"""Gathers what the LLM needs to know about an incident, as compact JSON-ready data.

Raw readings would be ~360 rows per metric for 30 minutes: too many tokens and hard for the
model to read. We send per-minute averages plus a few summary numbers instead.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from statistics import fmean, pstdev

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Comment, Incident, IncidentStatus, Metric, Rack, Server
from app.services import metrics as metrics_service
from app.services.detector import METRIC_NAMES

WINDOW = timedelta(minutes=30)
AFTER_OPENING = timedelta(minutes=5)  # how far past the incident's opening the window reaches
BASELINE_PART = timedelta(minutes=20)  # the window's first 20 min stand for "normal"
NEIGHBOUR_LOOKBACK = timedelta(minutes=1)
PAST_INCIDENTS = 5
NOTES_PER_INCIDENT = 3
NOTE_MAX_CHARS = 300

UNITS = {
    "cpu_temp": "°C",
    "power_w": "W",
    "disk_used_pct": "%",
    "memory_used_pct": "%",
    "network_mbps": "Mbps",
}


class MetricSummary(BaseModel):
    unit: str
    baseline_mean: float | None  # first 20 min of the window; None if no data then
    baseline_std: float | None
    latest: float
    minimum: float
    maximum: float
    per_minute: list[float]  # oldest first, one average per minute that has data


class NeighbourServer(BaseModel):
    hostname: str
    cpu_temp: float | None
    power_w: float | None
    active_incident: str | None


class PastIncident(BaseModel):
    title: str
    severity: str
    opened_at: datetime
    resolved_at: datetime | None
    notes: list[str]  # operators' comments, often how it was fixed


class IncidentFacts(BaseModel):
    title: str
    metric: str
    severity: str
    status: str
    opened_at: datetime
    detector_findings: list[str]


class ServerFacts(BaseModel):
    hostname: str
    rack: str
    rack_location: str


class DiagnosisContext(BaseModel):
    window_start: datetime
    window_end: datetime
    incident: IncidentFacts
    server: ServerFacts
    metrics: dict[str, MetricSummary]
    rack_neighbours: list[NeighbourServer]  # as of window_end
    similar_resolved_incidents: list[PastIncident]


def incident_window(incident: Incident, now: datetime) -> tuple[datetime, datetime]:
    """30 minutes around the incident: mostly before it, and up to 5 minutes after it opened.

    Anchored on the incident, not on "now": a diagnosis retried hours later must still look at
    what happened at the time, not at today's (probably normal) readings.
    """
    end = min(now, incident.created_at + AFTER_OPENING)
    return end - WINDOW, end


async def build_context(db: AsyncSession, incident: Incident) -> DiagnosisContext:
    start, end = incident_window(incident, datetime.now(UTC))
    server, rack = (
        await db.execute(select(Server, Rack).join(Rack).where(Server.id == incident.server_id))
    ).one()
    readings = await metrics_service.metric_history(db, server.id, start, end)
    return DiagnosisContext(
        window_start=start,
        window_end=end,
        incident=IncidentFacts(
            title=incident.title,
            metric=incident.metric_name,
            severity=incident.severity,
            status=incident.status,
            opened_at=incident.created_at,
            detector_findings=await _detector_findings(db, incident.id),
        ),
        server=ServerFacts(hostname=server.hostname, rack=rack.name, rack_location=rack.location),
        metrics=summarize(readings, start),
        rack_neighbours=await _neighbours(db, server, end),
        similar_resolved_incidents=await _similar_incidents(db, incident, end),
    )


def summarize(readings: Sequence[Metric], window_start: datetime) -> dict[str, MetricSummary]:
    """Per metric: baseline, extremes and per-minute averages. `readings` oldest first."""
    if not readings:
        return {}
    baseline_end = window_start + BASELINE_PART
    summaries = {}
    for name in METRIC_NAMES:
        values = [getattr(r, name) for r in readings]
        baseline = [getattr(r, name) for r in readings if r.timestamp < baseline_end]
        minutes: dict[int, list[float]] = {}
        for reading, value in zip(readings, values, strict=True):
            minute = int((reading.timestamp - window_start).total_seconds() // 60)
            minutes.setdefault(minute, []).append(value)
        summaries[name] = MetricSummary(
            unit=UNITS[name],
            baseline_mean=round(fmean(baseline), 1) if baseline else None,
            baseline_std=round(pstdev(baseline), 2) if baseline else None,
            latest=round(values[-1], 1),
            minimum=round(min(values), 1),
            maximum=round(max(values), 1),
            per_minute=[round(fmean(minutes[m]), 1) for m in sorted(minutes)],
        )
    return summaries


async def _detector_findings(db: AsyncSession, incident_id: int) -> list[str]:
    """The detector's own explanations, from the audit trail (opened + severity raised)."""
    stmt = (
        select(AuditLog.details)
        .where(
            AuditLog.entity_type == "incident",
            AuditLog.entity_id == incident_id,
            AuditLog.action.in_(["incident.opened", "incident.severity_raised"]),
        )
        .order_by(AuditLog.id)
    )
    reasons = []
    for details in await db.scalars(stmt):
        for finding in details.get("findings", [details]):
            if "reason" in finding:
                reasons.append(f"{finding['metric']}: {finding['reason']}")
    return reasons


async def _neighbours(db: AsyncSession, server: Server, at: datetime) -> list[NeighbourServer]:
    """Other servers in the same rack at time `at`: a shared pattern points to a shared cause.

    Values are each neighbour's newest reading in the minute before `at`; incidents are those
    open at `at` (opened before it, and not yet resolved then).
    """
    others = list(
        await db.scalars(
            select(Server)
            .where(Server.rack_id == server.rack_id, Server.id != server.id)
            .order_by(Server.rack_unit)
        )
    )
    rows = await db.scalars(
        select(Metric)
        .where(
            Metric.server_id.in_([o.id for o in others]),
            Metric.timestamp > at - NEIGHBOUR_LOOKBACK,
            Metric.timestamp <= at,
        )
        .order_by(Metric.timestamp)
    )
    latest = {reading.server_id: reading for reading in rows}  # oldest first: newest wins
    active = {
        incident.server_id: incident.title
        for incident in await db.scalars(
            select(Incident).where(
                Incident.server_id.in_([o.id for o in others]),
                Incident.created_at <= at,
                or_(Incident.resolved_at.is_(None), Incident.resolved_at > at),
            )
        )
    }
    return [
        NeighbourServer(
            hostname=other.hostname,
            cpu_temp=round(latest[other.id].cpu_temp, 1) if other.id in latest else None,
            power_w=round(latest[other.id].power_w, 1) if other.id in latest else None,
            active_incident=active.get(other.id),
        )
        for other in others
    ]


async def _similar_incidents(
    db: AsyncSession, incident: Incident, before: datetime
) -> list[PastIncident]:
    """Incidents on the same metric (any server) resolved before `before`, with their notes.

    Only those already resolved at the time, so a late retry doesn't learn from the future.
    """
    past = await db.scalars(
        select(Incident)
        .where(
            Incident.metric_name == incident.metric_name,
            Incident.status == IncidentStatus.RESOLVED,
            Incident.resolved_at < before,
            Incident.id != incident.id,
        )
        .order_by(Incident.resolved_at.desc())
        .limit(PAST_INCIDENTS)
    )
    result = []
    for old in past:
        notes = await db.scalars(
            select(Comment.body)
            .where(Comment.incident_id == old.id)
            .order_by(Comment.id)
            .limit(NOTES_PER_INCIDENT)
        )
        result.append(
            PastIncident(
                title=old.title,
                severity=old.severity,
                opened_at=old.created_at,
                resolved_at=old.resolved_at,
                notes=[note[:NOTE_MAX_CHARS] for note in notes],
            )
        )
    return result
