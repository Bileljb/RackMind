"""AI diagnosis with a fake LLM: success, every failure kind, context building, endpoints.

The real Groq API is never called here: tests must be fast, free, repeatable and able to
simulate timeouts or bad answers on demand.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import groq
import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import LLMError, to_llm_error
from app.ai.context import build_context
from app.core.queue import DIAGNOSE_JOB
from app.models import (
    Comment,
    Diagnosis,
    DiagnosisError,
    DiagnosisStatus,
    Incident,
    IncidentStatus,
    Role,
    Server,
    Severity,
    User,
)
from app.services.detection import run_detection
from app.services.diagnosis import RESULT_SCHEMA, run_diagnosis
from tests.conftest import FakeRedis
from tests.factories import series

VALID_ANSWER = {
    "probable_cause": "Cooling failure in rack R01.",
    "confidence": 0.7,
    "recommended_steps": ["Check the rack's cooling unit.", "Requires approval: move workloads."],
    "evidence": [{"metric": "cpu_temp", "observation": "cpu_temp rose from 45 to 80 °C."}],
}


class FakeLLM:
    """Returns a prepared answer (or raises a prepared error) and records what it was asked."""

    model = "fake-model"

    def __init__(self, answer: str | LLMError) -> None:
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    async def complete(self, system: str, user: str, schema: dict[str, Any]) -> str:
        self.calls.append({"system": system, "user": user, "schema": schema})
        if isinstance(self.answer, LLMError):
            raise self.answer
        return self.answer


@pytest.fixture
async def incident(db: AsyncSession, servers: list[Server]) -> Incident:
    """A fresh overheating incident on r01-srv01, with 30 minutes of readings behind it."""
    server = servers[0]
    db.add_all(series(server.id, 30, base={"cpu_temp": 82}))
    incident = Incident(
        server_id=server.id,
        title=f"High CPU temperature on {server.hostname}",
        metric_name="cpu_temp",
        severity=Severity.CRITICAL,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)  # load created_at
    return incident


async def test_valid_answer_is_stored(db: AsyncSession, incident: Incident) -> None:
    llm = FakeLLM(json.dumps(VALID_ANSWER))

    diagnosis = await run_diagnosis(db, incident.id, llm)

    assert diagnosis.status is DiagnosisStatus.SUCCEEDED
    assert diagnosis.probable_cause == VALID_ANSWER["probable_cause"]
    assert diagnosis.confidence == 0.7
    assert diagnosis.recommended_steps == VALID_ANSWER["recommended_steps"]
    assert diagnosis.evidence == VALID_ANSWER["evidence"]
    assert diagnosis.model == "fake-model"
    assert diagnosis.latency_ms is not None and diagnosis.finished_at is not None
    # What the model was given: our rules, the incident's data, and the schema to follow.
    [call] = llm.calls
    assert "never take actions" in call["system"]
    assert "r01-srv01" in call["user"] and '"cpu_temp"' in call["user"]
    assert call["schema"] == RESULT_SCHEMA


@pytest.mark.parametrize(
    "answer",
    [
        "not json at all",
        json.dumps({**VALID_ANSWER, "confidence": 1.5}),  # outside 0-1
        json.dumps({**VALID_ANSWER, "evidence": []}),  # no evidence
        json.dumps({**VALID_ANSWER, "recommended_steps": ["x"] * 6}),  # too many steps
        json.dumps({k: v for k, v in VALID_ANSWER.items() if k != "probable_cause"}),
        json.dumps(
            {**VALID_ANSWER, "evidence": [{"metric": "fan_rpm", "observation": "invented"}]}
        ),
        json.dumps({**VALID_ANSWER, "extra_field": "not allowed"}),
    ],
    ids=["not-json", "confidence", "no-evidence", "too-many-steps", "missing", "metric", "extra"],
)
async def test_invalid_answers_are_stored_as_failures(
    db: AsyncSession, incident: Incident, answer: str
) -> None:
    diagnosis = await run_diagnosis(db, incident.id, FakeLLM(answer))

    assert diagnosis.status is DiagnosisStatus.FAILED
    assert diagnosis.error is DiagnosisError.INVALID_OUTPUT
    assert diagnosis.probable_cause is None  # nothing unvalidated is ever shown


@pytest.mark.parametrize(
    "kind", [DiagnosisError.TIMEOUT, DiagnosisError.RATE_LIMITED, DiagnosisError.API_ERROR]
)
async def test_api_failures_are_stored(
    db: AsyncSession, incident: Incident, kind: DiagnosisError
) -> None:
    diagnosis = await run_diagnosis(db, incident.id, FakeLLM(LLMError(kind, "boom")))

    assert diagnosis.status is DiagnosisStatus.FAILED
    assert diagnosis.error is kind
    assert diagnosis.error_detail == "boom"


async def test_without_api_key_the_feature_says_so(db: AsyncSession, incident: Incident) -> None:
    diagnosis = await run_diagnosis(db, incident.id, None)

    assert diagnosis.status is DiagnosisStatus.FAILED
    assert diagnosis.error is DiagnosisError.NOT_CONFIGURED


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def _status_error(cls: type[groq.APIStatusError], code: int, message: str) -> groq.APIError:
    return cls(message, response=httpx.Response(code, request=_request()), body=None)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (groq.APITimeoutError(_request()), DiagnosisError.TIMEOUT),
        (_status_error(groq.RateLimitError, 429, "slow down"), DiagnosisError.RATE_LIMITED),
        (
            _status_error(groq.BadRequestError, 400, "Generated JSON does not match the schema"),
            DiagnosisError.INVALID_OUTPUT,
        ),
        (_status_error(groq.AuthenticationError, 401, "bad key"), DiagnosisError.API_ERROR),
        (_status_error(groq.InternalServerError, 503, "down"), DiagnosisError.API_ERROR),
        (groq.APIConnectionError(request=_request()), DiagnosisError.API_ERROR),
    ],
    ids=["timeout", "429", "schema-400", "401", "503", "connection"],
)
def test_sdk_errors_are_sorted_into_kinds(error: groq.APIError, kind: DiagnosisError) -> None:
    assert to_llm_error(error).kind is kind


async def test_opening_an_incident_queues_a_diagnosis(
    db: AsyncSession, servers: list[Server], redis: FakeRedis
) -> None:
    server = servers[0]
    db.add_all(series(server.id, 1, base={"cpu_temp": 85}))
    await db.commit()

    await run_detection(db, redis, [server.id])  # type: ignore[arg-type]

    incident = await db.scalar(select(Incident).where(Incident.server_id == server.id))
    assert incident is not None
    diagnosis = await db.scalar(select(Diagnosis).where(Diagnosis.incident_id == incident.id))
    assert diagnosis is not None and diagnosis.status is DiagnosisStatus.PENDING
    assert (DIAGNOSE_JOB, (incident.id,)) in redis.jobs


async def test_context_is_anchored_on_the_incident_not_now(
    db: AsyncSession, servers: list[Server]
) -> None:
    """Diagnosing a 3-hour-old incident must show the data from back then."""
    server, neighbour, _ = servers
    opened = datetime.now(UTC) - timedelta(hours=3)
    then = opened + timedelta(minutes=5)  # the window ends 5 min after opening
    db.add_all(series(server.id, 30, base={"cpu_temp": 85}, end=then))  # hot back then
    db.add_all(series(server.id, 10, base={"cpu_temp": 40}))  # normal now: must be ignored
    db.add_all(series(neighbour.id, 30, base={"cpu_temp": 84}, end=then, seed=1))
    old = Incident(
        server_id=server.id,
        title="Old one",
        metric_name="cpu_temp",
        severity=Severity.WARNING,
        status=IncidentStatus.RESOLVED,
        created_at=opened - timedelta(days=1),
        resolved_at=opened - timedelta(hours=20),
    )
    later = Incident(
        server_id=neighbour.id,
        title="Resolved after the incident",
        metric_name="cpu_temp",
        severity=Severity.WARNING,
        status=IncidentStatus.RESOLVED,
        created_at=opened + timedelta(minutes=30),
        resolved_at=opened + timedelta(hours=1),
    )
    incident = Incident(
        server_id=server.id,
        title="Hot",
        metric_name="cpu_temp",
        severity=Severity.CRITICAL,
        created_at=opened,
    )
    db.add_all([old, later, incident])
    await db.commit()
    db.add(Comment(incident_id=old.id, author_id=(await _any_user(db)).id, body="Fan replaced"))
    await db.commit()

    context = await build_context(db, incident)

    # The window ends 5 minutes after the incident opened, hours ago, not now.
    assert context.window_end == then
    cpu = context.metrics["cpu_temp"]
    assert 80 < cpu.latest < 90  # the readings from back then, not today's 40 °C
    assert [n.hostname for n in context.rack_neighbours] == ["r01-srv02"]
    assert 80 < (context.rack_neighbours[0].cpu_temp or 0) < 90
    assert [p.title for p in context.similar_resolved_incidents] == ["Old one"]
    assert context.similar_resolved_incidents[0].notes == ["Fan replaced"]


async def _any_user(db: AsyncSession) -> User:
    user = User(email="note@test.local", full_name="N", hashed_password="x", role=Role.OPERATOR)
    db.add(user)
    await db.commit()
    return user


# ---------- endpoints ----------

Login = Callable[[Role], User]


@pytest.fixture
async def diagnosed(db: AsyncSession, incident: Incident) -> Diagnosis:
    return await run_diagnosis(db, incident.id, FakeLLM(json.dumps(VALID_ANSWER)))


async def test_engineer_reads_the_diagnosis(
    client: AsyncClient, incident: Incident, diagnosed: Diagnosis, login: Login
) -> None:
    login(Role.ENGINEER)

    response = await client.get(f"/incidents/{incident.id}/diagnosis")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["probable_cause"] == VALID_ANSWER["probable_cause"]
    assert body["feedback"] == {"helpful": 0, "not_helpful": 0, "mine": None}


async def test_feedback_is_one_vote_per_user(
    client: AsyncClient, incident: Incident, diagnosed: Diagnosis, login: Login
) -> None:
    url = f"/incidents/{incident.id}/diagnosis/feedback"
    login(Role.ENGINEER)
    await client.put(url, json={"helpful": True})
    changed_mind = await client.put(url, json={"helpful": False})
    login(Role.ADMIN)
    admin_vote = await client.put(url, json={"helpful": True})

    assert changed_mind.json()["feedback"] == {"helpful": 0, "not_helpful": 1, "mine": False}
    assert admin_vote.json()["feedback"] == {"helpful": 1, "not_helpful": 1, "mine": True}


async def test_failed_diagnosis_cannot_be_rated_but_can_be_retried(
    client: AsyncClient, db: AsyncSession, incident: Incident, login: Login, redis: FakeRedis
) -> None:
    await run_diagnosis(db, incident.id, FakeLLM(LLMError(DiagnosisError.TIMEOUT, "slow")))
    login(Role.ENGINEER)
    base = f"/incidents/{incident.id}/diagnosis"

    rated = await client.put(f"{base}/feedback", json={"helpful": True})
    retried = await client.post(base)
    again = await client.post(base)

    assert rated.status_code == 409
    assert retried.status_code == 202
    assert retried.json()["status"] == "pending"
    assert retried.json()["error"] is None
    assert redis.jobs == [(DIAGNOSE_JOB, (incident.id,))]
    assert again.status_code == 409  # already pending: no duplicate job
    assert "incident.diagnosis_requested" in redis.actions()


async def test_retry_clears_votes_on_the_old_answer(
    client: AsyncClient, incident: Incident, diagnosed: Diagnosis, login: Login
) -> None:
    login(Role.ENGINEER)
    base = f"/incidents/{incident.id}/diagnosis"
    await client.put(f"{base}/feedback", json={"helpful": False})

    retried = await client.post(base)

    assert retried.json()["feedback"] == {"helpful": 0, "not_helpful": 0, "mine": None}


async def test_incident_without_diagnosis_is_404_until_requested(
    client: AsyncClient, incident: Incident, login: Login
) -> None:
    login(Role.ENGINEER)
    url = f"/incidents/{incident.id}/diagnosis"

    assert (await client.get(url)).status_code == 404
    assert (await client.post(url)).status_code == 202
    assert (await client.get(url)).json()["status"] == "pending"
