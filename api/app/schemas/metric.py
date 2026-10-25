from datetime import UTC, datetime, timedelta
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

# Readings slightly ahead of our clock are tolerated (clock drift between machines).
# Anything further ahead is a bad clock and would break "latest reading" queries.
MAX_CLOCK_SKEW = timedelta(minutes=5)

Percent = Annotated[float, Field(ge=0, le=100)]
NonNegative = Annotated[float, Field(ge=0)]


class MetricIn(BaseModel):
    """One reading sent by a server (or the simulator). Invalid fields -> HTTP 422."""

    server_id: int = Field(gt=0)
    # AwareDatetime rejects timestamps without a timezone ("2026-10-25T10:00:00"),
    # which would be ambiguous. Clients should send UTC, e.g. "2026-10-25T10:00:00Z".
    timestamp: AwareDatetime
    cpu_temp: float = Field(ge=-20, le=150, description="Degrees Celsius")
    power_w: NonNegative
    disk_used_pct: Percent
    memory_used_pct: Percent
    network_mbps: NonNegative

    @field_validator("timestamp")
    @classmethod
    def not_in_future(cls, value: datetime) -> datetime:
        if value > datetime.now(UTC) + MAX_CLOCK_SKEW:
            raise ValueError("timestamp is in the future")
        return value


class MetricOut(MetricIn):
    """A stored reading, as returned by the API."""

    # Lets Pydantic build this schema straight from a SQLAlchemy `Metric` object.
    model_config = ConfigDict(from_attributes=True)

    id: int


class BatchResult(BaseModel):
    inserted: int
