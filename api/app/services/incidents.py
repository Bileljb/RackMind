"""Incident workflow done by people: listing, lifecycle transitions, assignment, comments.

Lifecycle: open -> acknowledged -> resolved. Every change writes an audit entry.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Comment, Incident, IncidentStatus, Server, User
from app.schemas.incident import IncidentFilters
from app.services.audit import record_incident_event

# The only allowed move from each status. Resolved is final.
NEXT_STATUS = {
    IncidentStatus.OPEN: IncidentStatus.ACKNOWLEDGED,
    IncidentStatus.ACKNOWLEDGED: IncidentStatus.RESOLVED,
}


class InvalidTransitionError(Exception):
    def __init__(self, current: IncidentStatus, requested: IncidentStatus) -> None:
        super().__init__(f"Cannot move an incident from {current} to {requested}")


class ResolvedIncidentError(Exception):
    """A resolved incident is closed: it can be commented on, but not changed."""


class UnknownUserError(Exception):
    pass


async def list_incidents(db: AsyncSession, filters: IncidentFilters) -> list[Incident]:
    """Newest first. Every filter is optional; list filters match any of their values."""
    stmt = select(Incident)
    if filters.status:
        stmt = stmt.where(Incident.status.in_(filters.status))
    if filters.severity:
        stmt = stmt.where(Incident.severity.in_(filters.severity))
    if filters.server_id is not None:
        stmt = stmt.where(Incident.server_id == filters.server_id)
    if filters.rack_id is not None:
        stmt = stmt.join(Server).where(Server.rack_id == filters.rack_id)
    stmt = stmt.order_by(Incident.created_at.desc(), Incident.id.desc())
    return list(await db.scalars(stmt.limit(filters.limit).offset(filters.offset)))


async def get_incident(
    db: AsyncSession, incident_id: int, *, lock: bool = False
) -> Incident | None:
    """`lock=True` takes a row lock (SELECT ... FOR UPDATE) until commit, so two people acting
    on the same incident at once are handled one after the other instead of overwriting."""
    return await db.get(Incident, incident_id, with_for_update=lock)


async def incident_comments(db: AsyncSession, incident_id: int) -> list[Comment]:
    stmt = select(Comment).where(Comment.incident_id == incident_id).order_by(Comment.id)
    return list(await db.scalars(stmt))


async def incident_history(db: AsyncSession, incident_id: int) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == "incident", AuditLog.entity_id == incident_id)
        .order_by(AuditLog.id)
    )
    return list(await db.scalars(stmt))


async def change_status(
    db: AsyncSession, incident: Incident, requested: IncidentStatus, actor: User
) -> Incident:
    if NEXT_STATUS.get(incident.status) != requested:
        raise InvalidTransitionError(incident.status, requested)

    now = datetime.now(UTC)
    if requested is IncidentStatus.ACKNOWLEDGED:
        incident.acknowledged_at = now
    else:
        incident.resolved_at = now
    record_incident_event(
        db, incident.id, f"incident.{requested}", actor, previous=incident.status, status=requested
    )
    incident.status = requested
    await db.commit()
    return incident


async def assign(
    db: AsyncSession, incident: Incident, assignee_id: int | None, actor: User
) -> Incident:
    """Set or clear (`None`) who is working on the incident."""
    if incident.status is IncidentStatus.RESOLVED:
        raise ResolvedIncidentError
    if assignee_id is not None:
        assignee = await db.get(User, assignee_id)
        if assignee is None or not assignee.is_active:
            raise UnknownUserError
    record_incident_event(
        db,
        incident.id,
        "incident.assigned",
        actor,
        previous=incident.assignee_id,
        assignee_id=assignee_id,
    )
    incident.assignee_id = assignee_id
    await db.commit()
    return incident


async def add_comment(db: AsyncSession, incident: Incident, author: User, body: str) -> Comment:
    comment = Comment(incident_id=incident.id, author_id=author.id, body=body)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)  # load `created_at`, which Postgres filled in
    return comment
