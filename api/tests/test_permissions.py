"""Every role against every sensitive endpoint: the API is where permissions are enforced.

The web app hides buttons a role can't use, but that is only convenience: anyone can call
the API directly, so each rule below must hold even without the UI.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident, Role, Server, Severity, User
from tests.conftest import INGEST_HEADERS, reading


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str  # {server}, {incident} and {user} are filled in per test
    minimum: Role  # lowest role allowed; every role above it is allowed too
    body: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.method} {self.path}"


ENDPOINTS = [
    Endpoint("GET", "/auth/me", Role.OPERATOR),
    Endpoint("GET", "/racks", Role.OPERATOR),
    Endpoint("GET", "/servers", Role.OPERATOR),
    Endpoint("GET", "/servers/{server}", Role.OPERATOR),
    Endpoint("GET", "/servers/{server}/metrics", Role.OPERATOR),
    Endpoint("GET", "/metrics/latest", Role.OPERATOR),
    Endpoint("GET", "/incidents", Role.OPERATOR),
    Endpoint("GET", "/incidents/{incident}", Role.OPERATOR),
    Endpoint("POST", "/incidents/{incident}/acknowledge", Role.OPERATOR),
    Endpoint("POST", "/incidents/{incident}/comments", Role.OPERATOR, {"body": "on it"}),
    Endpoint("POST", "/incidents/{incident}/resolve", Role.ENGINEER),
    Endpoint("PUT", "/incidents/{incident}/assignee", Role.ENGINEER, {"assignee_id": None}),
    Endpoint("GET", "/incidents/{incident}/diagnosis", Role.ENGINEER),
    Endpoint("POST", "/incidents/{incident}/diagnosis", Role.ENGINEER),
    Endpoint("PUT", "/incidents/{incident}/diagnosis/feedback", Role.ENGINEER, {"helpful": True}),
    Endpoint("GET", "/simulation/status", Role.OPERATOR),
    Endpoint("POST", "/simulation/keepalive", Role.OPERATOR),
    Endpoint("DELETE", "/simulation/keepalive", Role.OPERATOR),
    Endpoint("GET", "/users/directory", Role.OPERATOR),
    Endpoint("GET", "/users", Role.ADMIN),
    Endpoint(
        "POST",
        "/users",
        Role.ADMIN,
        {"email": "new@x.io", "full_name": "New", "role": "operator", "password": "0123456789"},
    ),
    Endpoint("PATCH", "/users/{user}", Role.ADMIN, {"full_name": "Renamed"}),
]


@pytest.fixture
async def call(
    client: AsyncClient, db: AsyncSession, servers: list[Server], users: dict[Role, User]
) -> Callable[[Endpoint], Any]:
    """`await call(endpoint)` sends the request with real ids filled into the path."""
    incident = Incident(
        server_id=servers[0].id, title="t", metric_name="cpu_temp", severity=Severity.INFO
    )
    db.add(incident)
    await db.commit()
    ids = {"server": servers[0].id, "incident": incident.id, "user": users[Role.OPERATOR].id}

    async def send(endpoint: Endpoint) -> Any:
        path = endpoint.path.format(**ids)
        return await client.request(endpoint.method, path, json=endpoint.body)

    return send


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=str)
@pytest.mark.parametrize("role", list(Role), ids=str)
async def test_role_matrix(
    call: Callable[[Endpoint], Any],
    login: Callable[[Role], User],
    endpoint: Endpoint,
    role: Role,
) -> None:
    login(role)

    response = await call(endpoint)

    if role.rank >= endpoint.minimum.rank:
        # Allowed: whatever the outcome (200, 201, 409...), it was not refused for permissions.
        assert response.status_code not in (401, 403), response.text
    else:
        assert response.status_code == 403


@pytest.mark.parametrize(
    "endpoint", [*ENDPOINTS, Endpoint("GET", "/stream", Role.OPERATOR)], ids=str
)
async def test_logged_out_is_401_everywhere(
    call: Callable[[Endpoint], Any], endpoint: Endpoint
) -> None:
    assert (await call(endpoint)).status_code == 401


async def test_users_cannot_push_metrics_without_the_key(
    client: AsyncClient, servers: list[Server], login: Callable[[Role], User]
) -> None:
    login(Role.ADMIN)  # even an admin: ingestion is for the simulator only

    assert (await client.post("/metrics", json=reading(servers[0].id))).status_code == 401


async def test_simulator_key_reads_inventory_but_not_incidents(
    client: AsyncClient, servers: list[Server]
) -> None:
    client.headers.update(INGEST_HEADERS)

    assert (await client.get("/servers")).status_code == 200
    assert (await client.get("/racks")).status_code == 200
    assert (await client.get("/simulation/status")).status_code == 200
    assert (await client.post("/simulation/keepalive")).status_code == 401
    assert (await client.get("/incidents")).status_code == 401
    assert (await client.get("/metrics/latest")).status_code == 401
