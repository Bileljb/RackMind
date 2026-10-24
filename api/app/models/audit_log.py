from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AuditLog(TimestampMixin, Base):
    """Append-only record of who did what, e.g. `incident.acknowledged` on incident 42."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL actor means the system did it (e.g. the detector opening an incident).
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int]
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
