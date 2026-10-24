from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

# One engine per process: it owns the connection pool. Creating it does not connect yet;
# connections are opened lazily the first time a session runs a query.
engine = create_async_engine(str(get_settings().database_url), pool_pre_ping=True)

# Factory that builds a new AsyncSession on each call.
# expire_on_commit=False keeps loaded attributes usable after commit, which matters in async
# code: reading an expired attribute would trigger a hidden (and here forbidden) lazy query.
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
