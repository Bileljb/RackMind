from datetime import datetime

from sqlalchemy import insert, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Metric, Server
from app.schemas.metric import MetricIn


class UnknownServersError(Exception):
    def __init__(self, server_ids: set[int]) -> None:
        self.server_ids = sorted(server_ids)
        super().__init__(f"Unknown server ids: {self.server_ids}")


async def _check_servers_exist(db: AsyncSession, server_ids: set[int]) -> None:
    found = set(await db.scalars(select(Server.id).where(Server.id.in_(server_ids))))
    if missing := server_ids - found:
        raise UnknownServersError(missing)


async def ingest_metric(db: AsyncSession, reading: MetricIn) -> Metric:
    await _check_servers_exist(db, {reading.server_id})
    metric = Metric(**reading.model_dump())
    db.add(metric)
    await db.commit()
    return metric


async def ingest_metrics(db: AsyncSession, readings: list[MetricIn]) -> int:
    """Insert many readings in one round trip. All-or-nothing: one bad server id rejects all."""
    await _check_servers_exist(db, {r.server_id for r in readings})
    await db.execute(insert(Metric), [r.model_dump() for r in readings])
    await db.commit()
    return len(readings)


async def latest_metrics(db: AsyncSession, rack_id: int | None = None) -> list[Metric]:
    """The most recent reading of each server (servers with no readings are left out).

    Uses a LATERAL join: for each server row, run "its newest metric, LIMIT 1". Each of those
    is a quick lookup in the (server_id, timestamp) index, instead of scanning the whole table.
    """
    newest = (
        select(Metric)
        .where(Metric.server_id == Server.id)
        .order_by(Metric.timestamp.desc())
        .limit(1)
        .lateral()
    )
    stmt = select(aliased(Metric, newest)).select_from(Server).join(newest, true())
    if rack_id is not None:
        stmt = stmt.where(Server.rack_id == rack_id)
    return list(await db.scalars(stmt.order_by(Server.id)))


async def metric_history(
    db: AsyncSession, server_id: int, start: datetime, end: datetime
) -> list[Metric]:
    """Readings of one server with start <= timestamp < end, oldest first."""
    stmt = (
        select(Metric)
        .where(Metric.server_id == server_id, Metric.timestamp >= start, Metric.timestamp < end)
        .order_by(Metric.timestamp)
    )
    return list(await db.scalars(stmt))
