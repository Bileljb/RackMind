from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.deps import CurrentUser, DbSession
from app.models import Incident, IncidentStatus
from app.schemas.incident import (
    AssigneeIn,
    AuditEventOut,
    CommentIn,
    CommentOut,
    IncidentDetail,
    IncidentFilters,
    IncidentOut,
)
from app.services import incidents as incidents_service
from app.services.incidents import InvalidTransitionError, ResolvedIncidentError, UnknownUserError

router = APIRouter(prefix="/incidents", tags=["incidents"])


async def _incident_or_404(db: DbSession, incident_id: int, *, lock: bool = False) -> Incident:
    incident = await incidents_service.get_incident(db, incident_id, lock=lock)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return incident


async def _change_status(
    db: DbSession, incident_id: int, requested: IncidentStatus, actor: CurrentUser
) -> IncidentOut:
    incident = await _incident_or_404(db, incident_id, lock=True)
    try:
        incident = await incidents_service.change_status(db, incident, requested, actor)
    except InvalidTransitionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    return IncidentOut.model_validate(incident)


@router.get("")
async def list_incidents(
    db: DbSession, filters: Annotated[IncidentFilters, Query()]
) -> list[IncidentOut]:
    rows = await incidents_service.list_incidents(db, filters)
    return [IncidentOut.model_validate(row) for row in rows]


@router.get("/{incident_id}")
async def get_incident(incident_id: int, db: DbSession) -> IncidentDetail:
    incident = await _incident_or_404(db, incident_id)
    comments = await incidents_service.incident_comments(db, incident_id)
    history = await incidents_service.incident_history(db, incident_id)
    return IncidentDetail(
        incident=IncidentOut.model_validate(incident),
        comments=[CommentOut.model_validate(c) for c in comments],
        history=[AuditEventOut.model_validate(event) for event in history],
    )


@router.post("/{incident_id}/acknowledge")
async def acknowledge(incident_id: int, db: DbSession, actor: CurrentUser) -> IncidentOut:
    """open -> acknowledged: someone is looking at it. 409 from any other status."""
    return await _change_status(db, incident_id, IncidentStatus.ACKNOWLEDGED, actor)


@router.post("/{incident_id}/resolve")
async def resolve(incident_id: int, db: DbSession, actor: CurrentUser) -> IncidentOut:
    """acknowledged -> resolved: the problem is fixed. 409 from any other status."""
    return await _change_status(db, incident_id, IncidentStatus.RESOLVED, actor)


@router.put("/{incident_id}/assignee")
async def assign(
    incident_id: int, body: AssigneeIn, db: DbSession, actor: CurrentUser
) -> IncidentOut:
    incident = await _incident_or_404(db, incident_id, lock=True)
    try:
        incident = await incidents_service.assign(db, incident, body.assignee_id, actor)
    except ResolvedIncidentError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Incident is resolved") from error
    except UnknownUserError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Assignee is not an active user"
        ) from error
    return IncidentOut.model_validate(incident)


@router.post("/{incident_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    incident_id: int, body: CommentIn, db: DbSession, author: CurrentUser
) -> CommentOut:
    incident = await _incident_or_404(db, incident_id)
    comment = await incidents_service.add_comment(db, incident, author, body.body)
    return CommentOut.model_validate(comment)
