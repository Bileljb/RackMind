from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.queue import redis_settings
from app.routers import (
    auth,
    diagnosis,
    health,
    incidents,
    metrics,
    racks,
    servers,
    simulation,
    stream,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once: code before `yield` at startup, code after it at shutdown.

    One Redis connection pool for the whole process, shared by every request (see `get_redis`).
    """
    app.state.redis = await create_pool(redis_settings())
    yield
    await app.state.redis.aclose()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(racks.router)
app.include_router(servers.router)
app.include_router(incidents.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(stream.router)
app.include_router(diagnosis.router)
app.include_router(simulation.router)
