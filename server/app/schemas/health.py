from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response schema for GET /health."""

    status: str
    db: str
