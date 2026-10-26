"""Login, logout, session cookie and token checks."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import SESSION_COOKIE, create_access_token, hash_password
from app.models import Role, User

PASSWORD = "correct horse battery"


@pytest.fixture
async def alice(db: AsyncSession) -> User:
    user = User(
        email="alice@rackmind.local",
        full_name="Alice",
        hashed_password=hash_password(PASSWORD),
        role=Role.ENGINEER,
    )
    db.add(user)
    await db.commit()
    return user


async def test_login_sets_an_httponly_cookie_and_me_works(client: AsyncClient, alice: User) -> None:
    response = await client.post(
        "/auth/login", json={"email": " Alice@Rackmind.LOCAL ", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "alice@rackmind.local"
    assert "hashed_password" not in response.json()
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    me = await client.get("/auth/me")  # the client stored the cookie, like a browser
    assert me.json()["id"] == alice.id


@pytest.mark.parametrize(
    ("email", "password"),
    [("alice@rackmind.local", "wrong password"), ("nobody@rackmind.local", PASSWORD)],
)
async def test_bad_credentials_get_the_same_401(
    client: AsyncClient, alice: User, email: str, password: str
) -> None:
    response = await client.post("/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json()["detail"] == "Wrong email or password"
    assert SESSION_COOKIE not in client.cookies


async def test_inactive_user_cannot_log_in(
    client: AsyncClient, db: AsyncSession, alice: User
) -> None:
    alice.is_active = False
    await db.commit()

    response = await client.post("/auth/login", json={"email": alice.email, "password": PASSWORD})

    assert response.status_code == 401


async def test_logout_clears_the_cookie(client: AsyncClient, alice: User) -> None:
    await client.post("/auth/login", json={"email": alice.email, "password": PASSWORD})

    response = await client.post("/auth/logout")

    assert response.status_code == 204
    assert SESSION_COOKIE not in client.cookies
    assert (await client.get("/auth/me")).status_code == 401


async def test_deactivation_ends_an_existing_session_at_once(
    client: AsyncClient, db: AsyncSession, alice: User
) -> None:
    client.cookies.set(SESSION_COOKIE, create_access_token(alice.id))
    assert (await client.get("/auth/me")).status_code == 200

    alice.is_active = False
    await db.commit()

    assert (await client.get("/auth/me")).status_code == 401


def forged_token(user_id: int, *, secret: str, expires_in: timedelta) -> str:
    claims = {"sub": str(user_id), "exp": datetime.now(UTC) + expires_in}
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.mark.parametrize(
    "token_for",
    [
        lambda uid: forged_token(uid, secret="x" * 32, expires_in=timedelta(hours=1)),  # wrong key
        lambda uid: forged_token(
            uid,
            secret=get_settings().jwt_secret.get_secret_value(),
            expires_in=timedelta(seconds=-1),  # expired
        ),
        lambda uid: "not-a-jwt",
    ],
    ids=["forged", "expired", "garbage"],
)
async def test_invalid_tokens_are_rejected(
    client: AsyncClient, alice: User, token_for: Callable[[int], str]
) -> None:
    client.cookies.set(SESSION_COOKIE, token_for(alice.id))

    assert (await client.get("/auth/me")).status_code == 401
