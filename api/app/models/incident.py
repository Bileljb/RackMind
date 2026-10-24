from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, enum_column


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Incident(TimestampMixin, Base):
    """An anomaly on one server. `created_at` is when it was opened."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    metric_name: Mapped[str] = mapped_column(String(50))  # which metric triggered it
    severity: Mapped[Severity] = mapped_column(enum_column(Severity))
    status: Mapped[IncidentStatus] = mapped_column(
        enum_column(IncidentStatus), default=IncidentStatus.OPEN, index=True
    )
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
