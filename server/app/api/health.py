import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application and database health check",
)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Return application status and live database connectivity.

    Args:
        db: Injected async database session.

    Returns:
        HealthResponse with status and db fields.

    Raises:
        HTTPException 503: When the database is unreachable.
    """
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
        logger.info("Health check passed")
    except Exception as exc:
        db_status = "error"
        logger.error("Health check DB error", extra={"error": str(exc)})
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "ok", "db": db_status},
        )

    return HealthResponse(status="ok", db=db_status)
