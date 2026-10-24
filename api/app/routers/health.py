from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness check: answers as long as the API process is up."""
    return {"status": "ok"}
