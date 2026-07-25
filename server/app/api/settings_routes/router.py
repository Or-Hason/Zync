"""Combined settings API router."""

from fastapi import APIRouter

from app.api.settings_routes.blacklist import router as blacklist_router
from app.api.settings_routes.scan import router as scan_router
from app.api.settings_routes.template import router as template_router
from app.api.settings_routes.notifications import router as notifications_router

router = APIRouter(prefix="/settings", tags=["settings"])

router.include_router(blacklist_router)
router.include_router(scan_router)
router.include_router(template_router)
router.include_router(notifications_router)
