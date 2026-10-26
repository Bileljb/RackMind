from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, enum_column


class DiagnosisStatus(StrEnum):
    PENDING = "pending"  # queued for the AI worker
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DiagnosisError(StrEnum):
    """Why a diagnosis failed, so the UI can say something useful (and tests can check it)."""

    NOT_CONFIGURED = "not_configured"  # no GROQ_API_KEY
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    API_ERROR = "api_error"
    INVALID_OUTPUT = "invalid_output"  # the model's answer didn't match our schema


class Diagnosis(TimestampMixin, Base):
    """The AI's suggested cause and next steps for one incident. Only ever a suggestion."""

    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(primary_key=True)
    # One diagnosis per incident; "retry" overwrites it rather than adding rows.
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[DiagnosisStatus] = mapped_column(enum_column(DiagnosisStatus))
    model: Mapped[str | None] = mapped_column(String(100))
    probable_cause: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None]  # 0-1, the model's own estimate
    recommended_steps: Mapped[list[str]] = mapped_column(JSONB, default=list)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error: Mapped[DiagnosisError | None] = mapped_column(enum_column(DiagnosisError))
    error_detail: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None]  # how long the API call took
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DiagnosisFeedback(TimestampMixin, Base):
    """'Was this helpful?': one vote per user per diagnosis (voting again changes it)."""

    __tablename__ = "diagnosis_feedback"
    __table_args__ = (UniqueConstraint("diagnosis_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnosis_id: Mapped[int] = mapped_column(ForeignKey("diagnoses.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    helpful: Mapped[bool]
