from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.deps import Operator, Redis, require_user_or_ingest_key
from app.services import simulation

# Any logged-in user may start the simulation: exploring the demo changes no real data.
router = APIRouter(prefix="/simulation", tags=["simulation"])


class SimulationStatus(BaseModel):
    active: bool


@router.get("/status", dependencies=[Depends(require_user_or_ingest_key)])
async def get_status(redis: Redis) -> SimulationStatus:
    """Asked by the simulator before each cycle, and by the web app to show "Paused"."""
    return SimulationStatus(active=await simulation.is_active(redis))


@router.post("/keepalive", status_code=status.HTTP_204_NO_CONTENT)
async def keep_alive(redis: Redis, _: Operator) -> None:
    """Sent by the web app on entering Simulation mode, then every 30s while it stays there."""
    await simulation.keep_alive(redis)


@router.delete("/keepalive", status_code=status.HTTP_204_NO_CONTENT)
async def stop(redis: Redis, _: Operator) -> None:
    """Sent when the user switches back to Live, so the simulation stops without waiting."""
    await simulation.stop(redis)
