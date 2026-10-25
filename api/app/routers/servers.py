from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import AwareDatetime
from sqlalchemy import select

from app.deps import DbSession
from app.models import Server
from app.schemas.inventory import ServerOut
from app.schemas.metric import MetricOut
from app.services import metrics as metrics_service

DEFAULT_HISTORY_WINDOW = timedelta(hours=1)
# 24h at one reading per 5s is ~17k rows: enough for charts, small enough for one response.
MAX_HISTORY_WINDOW = timedelta(hours=24)

router = APIRouter(prefix="/servers", tags=["inventory"])


@router.get("")
async def list_servers(db: DbSession, rack_id: int | None = None) -> list[ServerOut]:
    stmt = select(Server).order_by(Server.rack_id, Server.rack_unit)
    if rack_id is not None:
        stmt = stmt.where(Server.rack_id == rack_id)
    servers = await db.scalars(stmt)
    return [ServerOut.model_validate(server) for server in servers]


@router.get("/{server_id}/metrics")
async def server_metric_history(
    server_id: int,
    db: DbSession,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
) -> list[MetricOut]:
    """Readings in [start, end), oldest first. Defaults to the last hour; max range is 24h."""
    end = end or datetime.now(UTC)
    start = start or end - DEFAULT_HISTORY_WINDOW
    if start >= end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "start must be before end")
    if end - start > MAX_HISTORY_WINDOW:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "time range is longer than 24h")
    if await db.get(Server, server_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")

    rows = await metrics_service.metric_history(db, server_id, start, end)
    return [MetricOut.model_validate(row) for row in rows]
