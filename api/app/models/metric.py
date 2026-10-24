from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Metric(Base):
    """One telemetry reading from one server at one point in time."""

    __tablename__ = "metrics"

    # BigInteger: this table grows fast (20 servers x 1 reading / 5s = ~350k rows/day).
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cpu_temp: Mapped[float]  # degrees Celsius
    power_w: Mapped[float]
    disk_used_pct: Mapped[float]
    memory_used_pct: Mapped[float]
    network_mbps: Mapped[float]
