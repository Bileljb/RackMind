"""Import every model here so `Base.metadata` knows all tables (Alembic relies on this)."""

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.comment import Comment
from app.models.diagnosis import Diagnosis, DiagnosisError, DiagnosisFeedback, DiagnosisStatus
from app.models.incident import Incident, IncidentStatus, Severity
from app.models.metric import Metric
from app.models.rack import Rack
from app.models.server import Server, ServerSource
from app.models.user import Role, User

__all__ = [
    "AuditLog",
    "Base",
    "Comment",
    "Diagnosis",
    "DiagnosisError",
    "DiagnosisFeedback",
    "DiagnosisStatus",
    "Incident",
    "IncidentStatus",
    "Metric",
    "Rack",
    "Role",
    "Server",
    "ServerSource",
    "Severity",
    "User",
]
