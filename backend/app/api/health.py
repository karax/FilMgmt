from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Report whether the API is running."""
    return {"status": "ok"}

