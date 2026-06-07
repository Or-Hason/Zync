from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.resumes import router as resumes_router
from app.api.resumes_active import router as resumes_active_router
from app.api.settings import router as settings_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
# Active-resume routes first so GET /resumes/active is matched before
# GET /resumes/{resume_id} captures "active" as an id.
api_router.include_router(resumes_active_router)
api_router.include_router(resumes_router)
api_router.include_router(jobs_router)
api_router.include_router(settings_router)
