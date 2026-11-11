from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.deps import DbSession, require_user_or_ingest_key
from app.models import Rack, Server, ServerSource
from app.schemas.inventory import RackOut

# Read by people (dashboard) and by the simulator, which uses its API key.
router = APIRouter(
    prefix="/racks", tags=["inventory"], dependencies=[Depends(require_user_or_ingest_key)]
)


@router.get("")
async def list_racks(db: DbSession, source: ServerSource | None = None) -> list[RackOut]:
    """All racks, or with `source` only those holding at least one server of that source."""
    stmt = select(Rack).order_by(Rack.name)
    if source is not None:
        stmt = stmt.where(Rack.id.in_(select(Server.rack_id).where(Server.source == source)))
    racks = await db.scalars(stmt)
    return [RackOut.model_validate(rack) for rack in racks]
