from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Metric(Base):
    """One telemetry reading from one server at one point in time."""

    __tablename__ = "metrics"
    # Almost every query is "one server, a time range" or "one server, newest reading".
    # This composite index serves both (Postgres can also read it backwards for DESC).
    __table_args__ = (Index("ix_metrics_server_id_timestamp", "server_id", "timestamp"),)

    # BigInteger: this table grows fast (20 servers x 1 reading / 5s = ~350k rows/day).
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # None = the server has no sensor for it (most VPSes have neither temperature nor power).
    cpu_temp: Mapped[float | None]  # degrees Celsius
    power_w: Mapped[float | None]
    # None on readings recorded before this metric was added.
    cpu_usage_pct: Mapped[float | None]
    disk_used_pct: Mapped[float]
    memory_used_pct: Mapped[float]
    network_mbps: Mapped[float]
