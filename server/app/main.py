import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.scheduler import start_scheduler, stop_scheduler

settings = get_settings()
setup_logging(settings.log_level)

logger = logging.getLogger(__name__)

# True while the test suite is importing/driving the app. The background
# scheduler must never start under pytest: it would spin up a real DB-hitting
# loop against the fake sessions the tests inject.
_UNDER_PYTEST = "pytest" in sys.modules


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    logger.info(
        "Zync API starting",
        extra={"env": settings.app_env, "db": settings.database_url_masked},
    )
    if not _UNDER_PYTEST:
        start_scheduler()
    yield
    if not _UNDER_PYTEST:
        stop_scheduler()
    logger.info("Zync API shutting down")


app = FastAPI(
    title="Zync API",
    version="0.1.0",
    description="AI-driven job hunting and application management backend.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Origins allowed to call the API from a browser context.
#
# The first two are the Vite dev servers (Tauri dev window / plain browser).
# The last two are the packaged desktop app: the bundled WebView serves the
# frontend from its own scheme, so every call to 127.0.0.1:8000 is cross-origin
# and is blocked outright without these. Windows (WebView2) reports
# `http://tauri.localhost`; macOS and Linux (WKWebView / WebKitGTK) report
# `tauri://localhost`. Both are listed so one build works on every platform.
#
# Loopback only, by design: the API is unauthenticated and serves resume PII,
# so no remote origin may ever be added here.
ALLOWED_ORIGINS = [
    "http://localhost:1420",
    "http://localhost:5173",
    "http://tauri.localhost",
    "tauri://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
