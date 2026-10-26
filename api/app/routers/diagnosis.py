from fastapi import APIRouter, HTTPException, status

from app.deps import DbSession, Engineer, Redis
from app.models import Diagnosis, Incident, User
from app.schemas.diagnosis import DiagnosisOut, FeedbackIn, FeedbackSummary
from app.services import diagnosis as diagnosis_service
from app.services.diagnosis import DiagnosisInProgressError, DiagnosisNotReadyError
from app.services.events import publish_incident_event

# Engineers and admins only: the plan reserves AI diagnosis details for them.
router = APIRouter(prefix="/incidents/{incident_id}/diagnosis", tags=["diagnosis"])


async def _incident_or_404(db: DbSession, incident_id: int) -> Incident:
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return incident


async def _diagnosis_or_404(db: DbSession, incident_id: int) -> Diagnosis:
    diagnosis = await diagnosis_service.get_diagnosis(db, incident_id)
    if diagnosis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No diagnosis for this incident")
    return diagnosis


async def _out(db: DbSession, diagnosis: Diagnosis, user: User) -> DiagnosisOut:
    helpful, not_helpful, mine = await diagnosis_service.feedback_summary(db, diagnosis, user)
    return DiagnosisOut.model_validate(
        {
            **{
                field: getattr(diagnosis, field)
                for field in DiagnosisOut.model_fields
                if field != "feedback"
            },
            "feedback": FeedbackSummary(helpful=helpful, not_helpful=not_helpful, mine=mine),
        }
    )


@router.get("")
async def get_diagnosis(incident_id: int, db: DbSession, user: Engineer) -> DiagnosisOut:
    """404 when the incident has none (incidents opened before AI diagnosis existed)."""
    await _incident_or_404(db, incident_id)
    return await _out(db, await _diagnosis_or_404(db, incident_id), user)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def request_diagnosis(
    incident_id: int, db: DbSession, redis: Redis, user: Engineer
) -> DiagnosisOut:
    """Ask again (after a failure, or for an older incident). 202: the result comes later."""
    incident = await _incident_or_404(db, incident_id)
    try:
        diagnosis = await diagnosis_service.request_again(db, redis, incident)
    except DiagnosisInProgressError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "A diagnosis is already running") from error
    await publish_incident_event(redis, "incident.diagnosis_requested", incident)
    return await _out(db, diagnosis, user)


@router.put("/feedback")
async def give_feedback(
    incident_id: int, body: FeedbackIn, db: DbSession, user: Engineer
) -> DiagnosisOut:
    """'Was this helpful?' One vote per user; voting again replaces it."""
    diagnosis = await _diagnosis_or_404(db, incident_id)
    try:
        await diagnosis_service.give_feedback(db, diagnosis, user, body.helpful)
    except DiagnosisNotReadyError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only a finished diagnosis can be rated"
        ) from error
    return await _out(db, diagnosis, user)
