from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import health

app = FastAPI(title=get_settings().app_name)
app.include_router(health.router)
