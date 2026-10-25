from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import health, metrics, racks, servers

app = FastAPI(title=get_settings().app_name)
app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(racks.router)
app.include_router(servers.router)
