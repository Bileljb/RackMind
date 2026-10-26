from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.deps import DbSession, require_user_or_ingest_key
from app.models import Rack
from app.schemas.inventory import RackOut

# Read by people (dashboard) and by the simulator, which uses its API key.
router = APIRouter(
    prefix="/racks", tags=["inventory"], dependencies=[Depends(require_user_or_ingest_key)]
)


@router.get("")
async def list_racks(db: DbSession) -> list[RackOut]:
    racks = await db.scalars(select(Rack).order_by(Rack.name))
    return [RackOut.model_validate(rack) for rack in racks]
