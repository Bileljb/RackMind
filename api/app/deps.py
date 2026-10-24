from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionFactory


async def get_db() -> AsyncIterator[AsyncSession]:
    """Give each request its own DB session, and close it when the request is done.

    Code before `yield` runs before the endpoint; code after it runs once the response is sent.
    Endpoints that write data call `await db.commit()` themselves.
    """
    async with SessionFactory() as session:
        yield session


# Shorthand for endpoint parameters: `async def handler(db: DbSession): ...`
DbSession = Annotated[AsyncSession, Depends(get_db)]
