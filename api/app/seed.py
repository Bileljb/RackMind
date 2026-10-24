"""Fill an empty database with demo data: 4 racks x 5 servers, and one user per role.

Run with `python -m app.seed`. Safe to run repeatedly: does nothing if racks already exist.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionFactory, engine
from app.core.security import hash_password
from app.models import Rack, Role, Server, User

RACK_COUNT = 4
SERVERS_PER_RACK = 5


def build_racks() -> list[Rack]:
    """Racks R01..R04 in two rows, each holding servers r01-srv01..r01-srv05 etc."""
    racks = []
    for rack_number in range(1, RACK_COUNT + 1):
        rack = Rack(name=f"R{rack_number:02d}", location=f"Row {'AB'[(rack_number - 1) // 2]}")
        rack.servers = [
            Server(hostname=f"r{rack_number:02d}-srv{slot:02d}", rack_unit=slot)
            for slot in range(1, SERVERS_PER_RACK + 1)
        ]
        racks.append(rack)
    return racks


def build_users(password: str) -> list[User]:
    hashed = hash_password(password)  # hashing is slow on purpose, so do it once for all 3
    return [
        User(
            email=f"{role.value}@rackmind.local",
            full_name=f"Demo {role.value.title()}",
            hashed_password=hashed,
            role=role,
        )
        for role in Role
    ]


async def seed(session: AsyncSession, password: str) -> bool:
    """Insert demo data. Returns False (and changes nothing) if data is already there."""
    if await session.scalar(select(Rack.id).limit(1)) is not None:
        return False
    session.add_all(build_racks())
    session.add_all(build_users(password))
    await session.commit()
    return True


async def main() -> None:
    password = get_settings().seed_password
    if password is None:
        raise SystemExit("SEED_PASSWORD is not set; add it to your .env file.")
    async with SessionFactory() as session:
        created = await seed(session, password.get_secret_value())
    await engine.dispose()
    print("Seed data created." if created else "Seed data already present, skipping.")


if __name__ == "__main__":
    asyncio.run(main())
