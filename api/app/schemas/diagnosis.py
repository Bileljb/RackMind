from datetime import datetime

from pydantic import BaseModel

from app.ai.schema import EvidenceItem
from app.models import DiagnosisError, DiagnosisStatus


class FeedbackSummary(BaseModel):
    helpful: int
    not_helpful: int
    mine: bool | None  # the current user's vote, None if they haven't voted


class DiagnosisOut(BaseModel):
    status: DiagnosisStatus
    model: str | None
    probable_cause: str | None
    confidence: float | None
    recommended_steps: list[str]
    evidence: list[EvidenceItem]
    error: DiagnosisError | None
    error_detail: str | None
    latency_ms: int | None
    created_at: datetime
    finished_at: datetime | None
    feedback: FeedbackSummary


class FeedbackIn(BaseModel):
    helpful: bool
