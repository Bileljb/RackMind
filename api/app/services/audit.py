from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


def record_incident_event(
    db: AsyncSession, incident_id: int, action: str, actor: User | None, **details: Any
) -> None:
    """Add an audit entry such as `incident.acknowledged` (saved with the caller's commit).

    `actor=None` means the system did it (the detector). `details` must be JSON-friendly.
    """
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            entity_type="incident",
            entity_id=incident_id,
            details=details,
        )
    )
