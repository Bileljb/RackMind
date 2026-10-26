from collections.abc import AsyncIterator
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionFactory
from app.models import User


async def get_db() -> AsyncIterator[AsyncSession]:
    """Give each request its own DB session, and close it when the request is done.

    Code before `yield` runs before the endpoint; code after it runs once the response is sent.
    Endpoints that write data call `await db.commit()` themselves.
    """
    async with SessionFactory() as session:
        yield session


# Shorthand for endpoint parameters: `async def handler(db: DbSession): ...`
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_queue(request: Request) -> ArqRedis:
    """The job queue opened at startup (see `lifespan` in main.py)."""
    queue: ArqRedis = request.app.state.queue
    return queue


Queue = Annotated[ArqRedis, Depends(get_queue)]


async def get_current_user(
    db: DbSession, x_user_id: Annotated[int | None, Header()] = None
) -> User:
    """Who is making the request.

    TEMPORARY until Phase 5: trusts an `X-User-Id` header, so anyone can act as anyone.
    Phase 5 replaces only this function's body (read the JWT cookie); endpoints stay the same.
    """
    user = await db.get(User, x_user_id) if x_user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Send an X-User-Id header with an active user's id"
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
