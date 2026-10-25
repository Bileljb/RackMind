from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

from app.deps import DbSession
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def ingest_one(reading: MetricIn, db: DbSession) -> MetricOut:
    try:
        metric = await metrics_service.ingest_metric(db, reading)
    except UnknownServersError as error:
        raise _unknown_servers(error) from error
    return MetricOut.model_validate(metric)


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def ingest_batch(
    readings: Annotated[list[MetricIn], Body(min_length=1, max_length=MAX_BATCH_SIZE)],
    db: DbSession,
) -> BatchResult:
    try:
        inserted = await metrics_service.ingest_metrics(db, readings)
    except UnknownServersError as error:
        raise _unknown_servers(error) from error
    return BatchResult(inserted=inserted)


@router.get("/latest")
async def latest(db: DbSession, rack_id: int | None = None) -> list[MetricOut]:
    """Newest reading of every server, optionally only for one rack (dashboard heatmap)."""
    rows = await metrics_service.latest_metrics(db, rack_id)
    return [MetricOut.model_validate(row) for row in rows]
