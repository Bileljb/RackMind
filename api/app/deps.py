from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionFactory
from app.core.security import SESSION_COOKIE, is_valid_ingest_key, read_access_token
from app.models import Role, User


async def get_db() -> AsyncIterator[AsyncSession]:
    """Give each request its own DB session, and close it when the request is done.

    Code before `yield` runs before the endpoint; code after it runs once the response is sent.
    Endpoints that write data call `await db.commit()` themselves.
    """
    async with SessionFactory() as session:
        yield session


# Shorthand for endpoint parameters: `async def handler(db: DbSession): ...`
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_redis(request: Request) -> ArqRedis:
    """The Redis client opened at startup (see `lifespan` in main.py): job queue and pub/sub."""
    redis: ArqRedis = request.app.state.redis
    return redis


Redis = Annotated[ArqRedis, Depends(get_redis)]

SessionToken = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]
ApiKey = Annotated[str | None, Header(alias="X-API-Key")]


async def get_current_user(db: DbSession, token: SessionToken = None) -> User:
    """The logged-in user, from the session cookie. 401 if missing, invalid or expired.

    The user is reloaded from the database on every request, so deactivating someone or
    changing their role takes effect at once.
    """
    user_id = read_access_token(token) if token else None
    user = await db.get(User, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum: Role) -> Callable[[User], Awaitable[User]]:
    """Build a dependency that lets through `minimum` and every role above it (403 otherwise).

    Usage: `user: Annotated[User, Depends(require_role(Role.ENGINEER))]`.
    Not logged in at all is still a 401, because `get_current_user` runs first.
    """

    async def check(user: CurrentUser) -> User:
        if user.role.rank < minimum.rank:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires the {minimum} role")
        return user

    return check


Operator = Annotated[User, Depends(require_role(Role.OPERATOR))]  # any logged-in user
Engineer = Annotated[User, Depends(require_role(Role.ENGINEER))]
Admin = Annotated[User, Depends(require_role(Role.ADMIN))]


async def require_ingest_key(key: ApiKey = None) -> None:
    """For machines, not people: the simulator proves itself with the shared `X-API-Key`."""
    if key is None or not is_valid_ingest_key(key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid X-API-Key")


async def require_user_or_ingest_key(
    db: DbSession, token: SessionToken = None, key: ApiKey = None
) -> None:
    """Inventory reads are needed by people (dashboard) and by the simulator (to know servers)."""
    if key is not None and is_valid_ingest_key(key):
        return
    await get_current_user(db, token)
