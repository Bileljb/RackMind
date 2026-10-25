from fastapi import APIRouter
from sqlalchemy import select

from app.deps import DbSession
from app.models import Rack
from app.schemas.inventory import RackOut

router = APIRouter(prefix="/racks", tags=["inventory"])


@router.get("")
async def list_racks(db: DbSession) -> list[RackOut]:
    racks = await db.scalars(select(Rack).order_by(Rack.name))
    return [RackOut.model_validate(rack) for rack in racks]
