"""Runs and stores AI diagnoses. The AI only suggests: nothing here acts on infrastructure.

Lifecycle of a diagnosis row: `pending` (job queued) -> `succeeded` or `failed` (with a reason).
Every failure is stored instead of raised, so the incident page can explain what happened.
"""

import logging
import time
from datetime import UTC, datetime

from arq.connections import ArqRedis
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import LLMClient, LLMError
from app.ai.context import build_context
from app.ai.prompt import SYSTEM_PROMPT, build_user_message
from app.ai.schema import DiagnosisResult
from app.core.queue import DIAGNOSE_JOB
from app.models import (
    Diagnosis,
    DiagnosisError,
    DiagnosisFeedback,
    DiagnosisStatus,
    Incident,
    User,
)

logger = logging.getLogger(__name__)

# The schema Groq must follow. Built once: it never changes while the app runs.
RESULT_SCHEMA = DiagnosisResult.model_json_schema()
ERROR_DETAIL_MAX_CHARS = 1000


class DiagnosisNotReadyError(Exception):
    """Feedback on a diagnosis that has not succeeded."""


class DiagnosisInProgressError(Exception):
    """A new diagnosis was requested while one is still pending."""


def add_pending(db: AsyncSession, incident_id: int) -> None:
    """Mark a new incident as waiting for a diagnosis (saved with the caller's commit)."""
    db.add(Diagnosis(incident_id=incident_id, status=DiagnosisStatus.PENDING))


async def enqueue(redis: ArqRedis, incident_id: int) -> None:
    """Queue the AI job. If Redis is down the diagnosis stays `pending`; retry from the UI."""
    try:
        await redis.enqueue_job(DIAGNOSE_JOB, incident_id)
    except RedisError:
        logger.warning("Could not queue diagnosis for incident %s", incident_id, exc_info=True)


async def get_diagnosis(db: AsyncSession, incident_id: int) -> Diagnosis | None:
    return await db.scalar(select(Diagnosis).where(Diagnosis.incident_id == incident_id))


async def request_again(db: AsyncSession, redis: ArqRedis, incident: Incident) -> Diagnosis:
    """Reset (or create, for incidents older than this feature) and queue a new diagnosis."""
    diagnosis = await get_diagnosis(db, incident.id)
    if diagnosis is None:
        diagnosis = Diagnosis(incident_id=incident.id)
        db.add(diagnosis)
    elif diagnosis.status is DiagnosisStatus.PENDING:
        raise DiagnosisInProgressError
    else:
        # Votes judged the previous answer; they say nothing about the next one.
        await db.execute(
            delete(DiagnosisFeedback).where(DiagnosisFeedback.diagnosis_id == diagnosis.id)
        )
    _reset(diagnosis)
    await db.commit()
    await enqueue(redis, incident.id)
    return diagnosis


async def run_diagnosis(db: AsyncSession, incident_id: int, llm: LLMClient | None) -> Diagnosis:
    """The worker job's body: build the context, ask the model, validate, store."""
    incident = await db.get_one(Incident, incident_id)
    diagnosis = await get_diagnosis(db, incident_id)
    if diagnosis is None:
        diagnosis = Diagnosis(incident_id=incident_id, status=DiagnosisStatus.PENDING)
        db.add(diagnosis)

    if llm is None:
        _fail(diagnosis, DiagnosisError.NOT_CONFIGURED, "No GROQ_API_KEY is set on the server")
    else:
        await _ask_model(db, diagnosis, incident, llm)
    diagnosis.finished_at = datetime.now(UTC)
    await db.commit()
    logger.info("Diagnosis of incident %s: %s", incident_id, diagnosis.error or diagnosis.status)
    return diagnosis


async def _ask_model(
    db: AsyncSession, diagnosis: Diagnosis, incident: Incident, llm: LLMClient
) -> None:
    context = await build_context(db, incident)
    diagnosis.model = llm.model
    started = time.perf_counter()
    try:
        raw = await llm.complete(SYSTEM_PROMPT, build_user_message(context), RESULT_SCHEMA)
    except LLMError as error:
        _fail(diagnosis, error.kind, str(error))
        return
    finally:
        diagnosis.latency_ms = round((time.perf_counter() - started) * 1000)

    try:
        # Validate again even though Groq enforced the schema: defense in depth, and it also
        # checks limits (lengths, 0-1 range) the way *we* define them.
        result = DiagnosisResult.model_validate_json(raw)
    except ValidationError as error:
        _fail(diagnosis, DiagnosisError.INVALID_OUTPUT, str(error))
        return

    diagnosis.status = DiagnosisStatus.SUCCEEDED
    diagnosis.probable_cause = result.probable_cause
    diagnosis.confidence = result.confidence
    diagnosis.recommended_steps = result.recommended_steps
    diagnosis.evidence = [item.model_dump() for item in result.evidence]


def _fail(diagnosis: Diagnosis, kind: DiagnosisError, detail: str) -> None:
    diagnosis.status = DiagnosisStatus.FAILED
    diagnosis.error = kind
    diagnosis.error_detail = detail[:ERROR_DETAIL_MAX_CHARS]


def _reset(diagnosis: Diagnosis) -> None:
    """Back to a blank `pending` row."""
    diagnosis.status = DiagnosisStatus.PENDING
    diagnosis.model = None
    diagnosis.probable_cause = None
    diagnosis.confidence = None
    diagnosis.recommended_steps = []
    diagnosis.evidence = []
    diagnosis.error = None
    diagnosis.error_detail = None
    diagnosis.latency_ms = None
    diagnosis.finished_at = None


async def give_feedback(db: AsyncSession, diagnosis: Diagnosis, user: User, helpful: bool) -> None:
    """Record or change this user's vote (one per user: upsert on the unique pair)."""
    if diagnosis.status is not DiagnosisStatus.SUCCEEDED:
        raise DiagnosisNotReadyError
    stmt = insert(DiagnosisFeedback).values(
        diagnosis_id=diagnosis.id, user_id=user.id, helpful=helpful
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["diagnosis_id", "user_id"], set_={"helpful": helpful}
    )
    await db.execute(stmt)
    await db.commit()


async def feedback_summary(
    db: AsyncSession, diagnosis: Diagnosis, user: User
) -> tuple[int, int, bool | None]:
    """(helpful votes, not helpful votes, this user's vote or None)."""
    rows = await db.execute(
        select(DiagnosisFeedback.helpful, func.count())
        .where(DiagnosisFeedback.diagnosis_id == diagnosis.id)
        .group_by(DiagnosisFeedback.helpful)
    )
    counts = {helpful: count for helpful, count in rows}
    mine = await db.scalar(
        select(DiagnosisFeedback.helpful).where(
            DiagnosisFeedback.diagnosis_id == diagnosis.id, DiagnosisFeedback.user_id == user.id
        )
    )
    return counts.get(True, 0), counts.get(False, 0), mine
