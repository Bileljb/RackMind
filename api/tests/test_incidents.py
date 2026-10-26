"""Incident endpoints: lifecycle, assignment, comments, filters, audit trail and live events.

Who may do what is tested in test_permissions.py; here each test logs in with a role allowed.
"""

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident, IncidentStatus, Role, Server, Severity, User
from tests.conftest import FakeRedis

Login = Callable[[Role], User]


def make_incident(server: Server, **overrides: object) -> Incident:
    values: dict[str, object] = {
        "server_id": server.id,
        "title": f"High CPU temperature on {server.hostname}",
        "metric_name": "cpu_temp",
        "severity": Severity.WARNING,
        **overrides,
    }
    return Incident(**values)


@pytest.fixture
async def incident(db: AsyncSession, servers: list[Server]) -> Incident:
    incident = make_incident(servers[0])
    db.add(incident)
    await db.commit()
    return incident


async def test_full_lifecycle_is_audited_and_published(
    client: AsyncClient, incident: Incident, login: Login, redis: FakeRedis
) -> None:
    url = f"/incidents/{incident.id}"

    operator = login(Role.OPERATOR)
    acked = await client.post(f"{url}/acknowledge")
    engineer = login(Role.ENGINEER)
    resolved = await client.post(f"{url}/resolve")

    assert acked.status_code == 200
    assert acked.json()["status"] == "acknowledged"
    assert acked.json()["acknowledged_at"] is not None
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None
    history = (await client.get(url)).json()["history"]
    assert [(e["action"], e["actor_id"], e["details"]) for e in history] == [
        ("incident.acknowledged", operator.id, {"previous": "open", "status": "acknowledged"}),
        ("incident.resolved", engineer.id, {"previous": "acknowledged", "status": "resolved"}),
    ]
    assert redis.actions() == ["incident.acknowledged", "incident.resolved"]
    assert {channel for channel, _ in redis.published} == {"incidents"}


@pytest.mark.parametrize(
    ("current", "action"),
    [
        (IncidentStatus.OPEN, "resolve"),  # must be acknowledged first
        (IncidentStatus.ACKNOWLEDGED, "acknowledge"),
        (IncidentStatus.RESOLVED, "acknowledge"),
        (IncidentStatus.RESOLVED, "resolve"),
    ],
)
async def test_invalid_transitions_are_409(
    client: AsyncClient,
    db: AsyncSession,
    servers: list[Server],
    login: Login,
    redis: FakeRedis,
    current: IncidentStatus,
    action: str,
) -> None:
    incident = make_incident(servers[0], status=current)
    db.add(incident)
    await db.commit()
    login(Role.ENGINEER)

    response = await client.post(f"/incidents/{incident.id}/{action}")

    assert response.status_code == 409
    assert redis.published == []  # nothing changed, nothing announced


async def test_assign_and_unassign(
    client: AsyncClient, incident: Incident, users: dict[Role, User], login: Login
) -> None:
    login(Role.ADMIN)
    engineer = users[Role.ENGINEER]
    url = f"/incidents/{incident.id}/assignee"

    assigned = await client.put(url, json={"assignee_id": engineer.id})
    cleared = await client.put(url, json={"assignee_id": None})
    unknown = await client.put(url, json={"assignee_id": 9999})

    assert assigned.json()["assignee_id"] == engineer.id
    assert cleared.json()["assignee_id"] is None
    assert unknown.status_code == 422
    history = (await client.get(f"/incidents/{incident.id}")).json()["history"]
    assert [e["details"] for e in history] == [
        {"previous": None, "assignee_id": engineer.id},
        {"previous": engineer.id, "assignee_id": None},
    ]


async def test_resolved_incident_cannot_be_reassigned(
    client: AsyncClient,
    db: AsyncSession,
    servers: list[Server],
    users: dict[Role, User],
    login: Login,
) -> None:
    incident = make_incident(servers[0], status=IncidentStatus.RESOLVED)
    db.add(incident)
    await db.commit()
    login(Role.ADMIN)

    response = await client.put(
        f"/incidents/{incident.id}/assignee", json={"assignee_id": users[Role.ENGINEER].id}
    )

    assert response.status_code == 409


async def test_comments(
    client: AsyncClient, incident: Incident, login: Login, redis: FakeRedis
) -> None:
    operator = login(Role.OPERATOR)
    url = f"/incidents/{incident.id}/comments"

    created = await client.post(url, json={"body": "  Fans look stuck  "})
    blank = await client.post(url, json={"body": "   "})

    assert created.status_code == 201
    assert created.json()["body"] == "Fans look stuck"
    assert blank.status_code == 422
    comments = (await client.get(f"/incidents/{incident.id}")).json()["comments"]
    assert [(c["author_id"], c["body"]) for c in comments] == [(operator.id, "Fans look stuck")]
    assert redis.actions() == ["incident.commented"]


async def test_recovery_suggestion_is_exposed(
    client: AsyncClient, db: AsyncSession, incident: Incident, login: Login
) -> None:
    login(Role.OPERATOR)
    before = (await client.get(f"/incidents/{incident.id}")).json()["incident"]
    incident.recovered_at = incident.created_at
    await db.commit()
    after = (await client.get(f"/incidents/{incident.id}")).json()["incident"]

    assert before["recovery_suggested"] is False
    assert after["recovery_suggested"] is True


async def test_list_filters_newest_first(
    client: AsyncClient, db: AsyncSession, servers: list[Server], login: Login
) -> None:
    login(Role.OPERATOR)
    r01_a, r01_b, r02 = servers
    rows = [
        make_incident(r01_a, status=IncidentStatus.RESOLVED, severity=Severity.INFO),
        make_incident(r01_b, status=IncidentStatus.ACKNOWLEDGED, severity=Severity.CRITICAL),
        make_incident(r02, severity=Severity.WARNING),
    ]
    for row in rows:  # one commit each, so ids follow creation order
        db.add(row)
        await db.commit()
    oldest, middle, newest = (row.id for row in rows)

    async def ids(**params: str | int | list[str]) -> list[int]:
        response = await client.get("/incidents", params=params)
        assert response.status_code == 200
        return [row["id"] for row in response.json()]

    assert await ids() == [newest, middle, oldest]
    assert await ids(status=["open", "acknowledged"]) == [newest, middle]
    assert await ids(severity="critical") == [middle]
    assert await ids(rack_id=r01_a.rack_id) == [middle, oldest]
    assert await ids(server_id=r02.id) == [newest]
    assert await ids(limit=1, offset=1) == [middle]


async def test_list_rejects_bad_filters(client: AsyncClient, login: Login) -> None:
    login(Role.OPERATOR)
    for params in ({"status": "closed"}, {"limit": 0}, {"limit": 201}):
        assert (await client.get("/incidents", params=params)).status_code == 422


async def test_unknown_incident_is_404(client: AsyncClient, login: Login) -> None:
    login(Role.ADMIN)

    assert (await client.get("/incidents/9999")).status_code == 404
    assert (await client.post("/incidents/9999/acknowledge")).status_code == 404
