from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, enum_column


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """0, 1, 2 for info, warning, critical. Use it to compare: string order would be wrong."""
        return list(Severity).index(self)


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Incident(TimestampMixin, Base):
    """An anomaly on one server. `created_at` is when it was opened."""

    __tablename__ = "incidents"
    __table_args__ = (
        # Deduplication rule: at most one active (not resolved) incident per server. Postgres
        # enforces it, so two detection jobs running at the same moment can't both open one.
        Index(
            "uq_incidents_active_server",
            "server_id",
            unique=True,
            postgresql_where=text("status <> 'resolved'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    metric_name: Mapped[str] = mapped_column(String(50))  # which metric triggered it
    severity: Mapped[Severity] = mapped_column(enum_column(Severity))  # highest seen so far
    status: Mapped[IncidentStatus] = mapped_column(
        enum_column(IncidentStatus), default=IncidentStatus.OPEN, index=True
    )
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set by the detector when the server's metrics look normal again (cleared if the anomaly
    # comes back). Only a suggestion: a person still decides to resolve.
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
