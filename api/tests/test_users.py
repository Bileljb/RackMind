"""Admin user management. Who may call these endpoints is in test_permissions.py."""

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Role, User

Login = Callable[[Role], User]

NEW_USER = {
    "email": "Bob@Rackmind.local",
    "full_name": "Bob",
    "role": "operator",
    "password": "a long enough password",
}


@pytest.fixture(autouse=True)
def as_admin(login: Login) -> User:
    return login(Role.ADMIN)


async def test_admin_creates_a_user_who_can_log_in(client: AsyncClient) -> None:
    created = await client.post("/users", json=NEW_USER)
    login = await client.post(
        "/auth/login", json={"email": "bob@rackmind.local", "password": NEW_USER["password"]}
    )

    assert created.status_code == 201
    assert created.json()["email"] == "bob@rackmind.local"  # stored lowercase
    assert "password" not in created.json() and "hashed_password" not in created.json()
    assert login.status_code == 200


@pytest.mark.parametrize(
    "overrides",
    [{"password": "short"}, {"email": "not-an-email"}, {"role": "superuser"}, {"full_name": " "}],
)
async def test_create_validates_input(client: AsyncClient, overrides: dict[str, str]) -> None:
    response = await client.post("/users", json={**NEW_USER, **overrides})

    assert response.status_code == 422


async def test_duplicate_email_is_409(client: AsyncClient) -> None:
    await client.post("/users", json=NEW_USER)

    duplicate = await client.post("/users", json={**NEW_USER, "email": "BOB@rackmind.local"})

    assert duplicate.status_code == 409


async def test_update_role_deactivate_and_reset_password(
    client: AsyncClient, db: AsyncSession, users: dict[Role, User], as_admin: User
) -> None:
    operator = users[Role.OPERATOR]
    url = f"/users/{operator.id}"

    promoted = await client.patch(url, json={"role": "engineer"})
    deactivated = await client.patch(url, json={"is_active": False})
    reset = await client.patch(url, json={"password": "brand new password"})

    assert promoted.json()["role"] == "engineer"
    assert deactivated.json()["is_active"] is False
    assert reset.status_code == 200
    audit = await db.scalars(
        select(AuditLog).where(AuditLog.entity_type == "user").order_by(AuditLog.id)
    )
    assert [(a.action, a.actor_id, a.details) for a in audit] == [
        ("user.updated", as_admin.id, {"role": "engineer"}),
        ("user.updated", as_admin.id, {"is_active": False}),
        ("user.updated", as_admin.id, {"password": "reset"}),  # never the password itself
    ]


@pytest.mark.parametrize("change", [{"role": "engineer"}, {"is_active": False}])
async def test_admin_cannot_lock_themselves_out(
    client: AsyncClient, as_admin: User, change: dict[str, object]
) -> None:
    response = await client.patch(f"/users/{as_admin.id}", json=change)

    assert response.status_code == 409


async def test_unknown_user_is_404(client: AsyncClient) -> None:
    assert (await client.patch("/users/9999", json={"full_name": "X"})).status_code == 404


async def test_directory_shows_names_without_emails(
    client: AsyncClient, users: dict[Role, User], login: Login
) -> None:
    login(Role.OPERATOR)

    response = await client.get("/users/directory")

    assert response.status_code == 200
    assert {u["full_name"] for u in response.json()} == {u.full_name for u in users.values()}
    assert all("email" not in u for u in response.json())
