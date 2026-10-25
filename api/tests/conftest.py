from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import URL, make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import get_settings
from app.deps import get_db
from app.main import app
from app.models import Base, Rack, Server


def _test_database_url() -> URL:
    """Same server as the app, but a separate `<name>_test` database: dev data is never touched."""
    url = make_url(str(get_settings().database_url))
    return url.set(database=f"{url.database}_test")


async def _create_database_if_missing(url: URL) -> None:
    # CREATE DATABASE can't run inside a transaction, hence AUTOCOMMIT on the `postgres` DB.
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        query = text("SELECT 1 FROM pg_database WHERE datname = :name")
        if await conn.scalar(query, {"name": url.database}) is None:
            await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    await admin.dispose()


@pytest.fixture(scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Once per test run: make sure the test DB exists and rebuild its tables from the models."""
    url = _test_database_url()
    await _create_database_if_missing(url)
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is rolled back after the test.

    "create_savepoint" turns the code's `commit()` calls into savepoints, so endpoints behave
    normally, yet nothing survives the test: every test starts with empty tables.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        yield session
        await session.close()
        await conn.rollback()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP client that calls the FastAPI app in-process, using the test session above."""

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def servers(db: AsyncSession) -> list[Server]:
    """Two racks: R01 holds two servers, R02 holds one."""
    rack_1 = Rack(name="R01", location="Row A")
    rack_1.servers = [
        Server(hostname="r01-srv01", rack_unit=1),
        Server(hostname="r01-srv02", rack_unit=2),
    ]
    rack_2 = Rack(name="R02", location="Row A")
    rack_2.servers = [Server(hostname="r02-srv01", rack_unit=1)]
    db.add_all([rack_1, rack_2])
    await db.commit()
    return [*rack_1.servers, *rack_2.servers]


def reading(server_id: int, timestamp: datetime | None = None, **overrides: Any) -> dict[str, Any]:
    """A valid metric payload; pass keyword overrides to make it invalid."""
    return {
        "server_id": server_id,
        "timestamp": (timestamp or datetime.now(UTC)).isoformat(),
        "cpu_temp": 45.0,
        "power_w": 300.0,
        "disk_used_pct": 40.0,
        "memory_used_pct": 50.0,
        "network_mbps": 200.0,
        **overrides,
    }
