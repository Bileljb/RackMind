from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.queue import redis_settings
from app.routers import health, incidents, metrics, racks, servers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once: code before `yield` at startup, code after it at shutdown.

    One Redis connection pool for the whole process, shared by every request (see `get_queue`).
    """
    app.state.queue = await create_pool(redis_settings())
    yield
    await app.state.queue.aclose()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(racks.router)
app.include_router(servers.router)
app.include_router(incidents.router)
