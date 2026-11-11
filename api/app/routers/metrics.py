from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.queue import request_detection
from app.deps import DbSession, Operator, Redis, require_ingest_key
from app.models import ServerSource
from app.schemas.metric import BatchResult, MetricIn, MetricOut
from app.services import metrics as metrics_service
from app.services.metrics import UnknownServersError

# The simulator sends 20 readings every 5s; this cap keeps one request from being huge.
MAX_BATCH_SIZE = 1000

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _unknown_servers(error: UnknownServersError) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"message": "Unknown server ids", "server_ids": error.server_ids},
    )


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_ingest_key)])
async def ingest_one(reading: MetricIn, db: DbSession, redis: Redis) -> MetricOut:
    try:
        metric = await metrics_service.ingest_metric(db, reading)
    except UnknownServersError as error:
        raise _unknown_servers(error) from error
    await request_detection(redis, [reading.server_id])
    return MetricOut.model_validate(metric)


@router.post(
    "/batch", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_ingest_key)]
)
async def ingest_batch(
    readings: Annotated[list[MetricIn], Body(min_length=1, max_length=MAX_BATCH_SIZE)],
    db: DbSession,
    redis: Redis,
) -> BatchResult:
    try:
        inserted = await metrics_service.ingest_metrics(db, readings)
    except UnknownServersError as error:
        raise _unknown_servers(error) from error
    # Detection runs in the worker, so this request returns as soon as the data is saved.
    await request_detection(redis, (r.server_id for r in readings))
    return BatchResult(inserted=inserted)


@router.get("/latest")
async def latest(
    db: DbSession, _: Operator, rack_id: int | None = None, source: ServerSource | None = None
) -> list[MetricOut]:
    """Newest reading of every server, optionally only for one rack or source (dashboard)."""
    rows = await metrics_service.latest_metrics(db, rack_id=rack_id, source=source)
    return [MetricOut.model_validate(row) for row in rows]
