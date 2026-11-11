from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

from app.models import IncidentStatus, ServerSource, Severity


class IncidentFilters(BaseModel):
    """Query parameters of `GET /incidents`, e.g. `?status=open&status=acknowledged&limit=20`."""

    status: list[IncidentStatus] = []
    severity: list[Severity] = []
    server_id: int | None = None
    rack_id: int | None = None
    source: ServerSource | None = None  # Live mode asks for "agent", Simulation for "simulated"
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: int
    title: str
    metric_name: str
    severity: Severity
    status: IncidentStatus
    assignee_id: int | None
    created_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    recovered_at: datetime | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recovery_suggested(self) -> bool:
        """Metrics look normal again: someone may want to resolve this incident."""
        return self.recovered_at is not None and self.status is not IncidentStatus.RESOLVED


class CommentIn(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    body: str
    created_at: datetime


class AuditEventOut(BaseModel):
    """One line of an incident's history, e.g. `incident.acknowledged` by user 2."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None  # None: done by the system (detector)
    action: str
    details: dict[str, Any]
    created_at: datetime


class IncidentDetail(BaseModel):
    incident: IncidentOut
    comments: list[CommentOut]
    history: list[AuditEventOut]


class AssigneeIn(BaseModel):
    assignee_id: int | None  # None unassigns


class IncidentEvent(BaseModel):
    """Pushed to live dashboards (SSE) when an incident changes, e.g. `incident.opened`."""

    action: str
    incident: IncidentOut
