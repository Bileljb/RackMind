"""Register a real server, so its agent may send readings for it.

    python -m app.add_server web-01 --group Production
    docker compose exec api python -m app.add_server web-01 --group Production

Prints the new server's id: put it in the agent's RACKMIND_SERVER_ID. The group (a rack in
the database) is created on first use and shows as a column on the dashboard.
"""

import argparse
import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionFactory, engine
from app.models import Rack, Server, ServerSource

DEFAULT_LOCATION = "Real servers"


class HostnameTakenError(Exception):
    pass


async def add_server(
    session: AsyncSession, hostname: str, group: str, location: str = DEFAULT_LOCATION
) -> Server:
    """Create an `agent` server in `group` (created if missing), in the group's next free slot."""
    if await session.scalar(select(Server.id).where(Server.hostname == hostname)) is not None:
        raise HostnameTakenError(hostname)
    rack = await session.scalar(select(Rack).where(Rack.name == group))
    if rack is None:
        rack = Rack(name=group, location=location)
        session.add(rack)
        await session.flush()  # sends the INSERT now, so `rack.id` is known
    top_slot = await session.scalar(
        select(func.max(Server.rack_unit)).where(Server.rack_id == rack.id)
    )
    server = Server(
        rack_id=rack.id,
        hostname=hostname,
        rack_unit=(top_slot or 0) + 1,
        source=ServerSource.AGENT,
    )
    session.add(server)
    await session.commit()
    return server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.add_server", description=__doc__)
    parser.add_argument("hostname", help="name shown on the dashboard, e.g. web-01")
    parser.add_argument("--group", required=True, help="group (rack) to put it in")
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="used for a new group")
    return parser.parse_args(argv)


async def main() -> None:
    args = parse_args()
    async with SessionFactory() as session:
        try:
            server = await add_server(session, args.hostname, args.group, args.location)
        except HostnameTakenError:
            raise SystemExit(f"A server named {args.hostname!r} already exists.") from None
    await engine.dispose()
    print(f"Added {server.hostname} to {args.group}. Agent setting: RACKMIND_SERVER_ID={server.id}")


if __name__ == "__main__":
    asyncio.run(main())
