from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.resumes import router as resumes_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(resumes_router)
