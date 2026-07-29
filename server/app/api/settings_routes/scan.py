"""Scan control endpoints."""

import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.resumes_active import load_active_resume
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, get_db
from app.schemas.settings import ScanSettings
from app.scraper.jobmaster import run_scan
from app.services.gemini_client import get_gemini_client
from app.services.ollama_client import get_ollama_client
from app.services.settings_store import SettingsStore, get_settings_store
from pydantic import BaseModel

class ManualScanPayload(BaseModel):
    manual_threshold: int | None = None

router = APIRouter()
logger = logging.getLogger(__name__)

NO_ACTIVE_RESUME_SCAN_MESSAGE = (
    "An active resume is required to enable auto-scanning. "
    "Please upload or select a resume first."
)

async def _run_manual_scan(manual_threshold: int | None = None) -> None:
    """Background coroutine: execute a full scan and clear the in-progress flag.
    
    Opens its own DB session so it can outlive the HTTP request that spawned it.
    Always clears ``scan_in_progress`` in a finally block even on failure.
    """
    cfg = get_settings()
    try:
        async with AsyncSessionLocal() as db:
            store = SettingsStore(db)
            scan_cfg = await store.get_scan_settings()
            try:
                gemini = get_gemini_client()
            except ValueError:
                logger.warning("Manual scan skipped — Gemini is not configured.")
                return
            await run_scan(
                db=db,
                ollama=get_ollama_client(),
                gemini=gemini,
                store=store,
                base_url=cfg.jobmaster_base_url,
                initial_limit=cfg.initial_scan_limit,
                max_per_scan=cfg.max_jobs_per_scan,
                notification_threshold=manual_threshold if manual_threshold is not None else scan_cfg["notification_score_threshold"],
                is_manual=True,
            )
            await store.set_last_scan_at(datetime.now(timezone.utc).isoformat())
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Manual scan failed.")
    finally:
        try:
            async with AsyncSessionLocal() as db:
                store = SettingsStore(db)
                await store.set_scan_in_progress(False)
                await db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to clear scan_in_progress flag.")


@router.post(
    "/scan/trigger",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an immediate background scan",
)
async def trigger_manual_scan(
    payload: ManualScanPayload | None = None,
    store: SettingsStore = Depends(get_settings_store),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Start a scan immediately, bypassing the auto-scan schedule.
    
    Resets the scan-due timer so the scheduler will not double-fire within
    the same frequency window. Returns 409 if a scan is already running, or
    400 when no active resume exists.
    """
    if await store.get_scan_in_progress():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scan is already in progress. Please wait for it to finish.",
        )
    if await load_active_resume(db) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_ACTIVE_RESUME_SCAN_MESSAGE,
        )
    await store.set_scan_in_progress(True)
    await db.commit()
    threshold = payload.manual_threshold if payload else None
    asyncio.create_task(_run_manual_scan(threshold))
    logger.info("Manual scan triggered.")
    return {"status": "started"}


@router.get(
    "/scan",
    response_model=ScanSettings,
    summary="Get the auto-scan configuration",
)
async def get_scan_settings(
    store: SettingsStore = Depends(get_settings_store),
) -> ScanSettings:
    """Return the persisted auto-scan configuration."""
    return ScanSettings(**await store.get_scan_settings())


@router.put(
    "/scan",
    response_model=ScanSettings,
    summary="Update the auto-scan configuration",
)
async def update_scan_settings(
    payload: ScanSettings,
    store: SettingsStore = Depends(get_settings_store),
    db: AsyncSession = Depends(get_db),
) -> ScanSettings:
    """Persist the auto-scan configuration.
    
    Enabling auto-scan requires an active resume (the scraper reads the search
    role from it); attempting to enable without one is rejected so background
    scanning can never run in a silently broken state.
    Raises:
        HTTPException: 400 when ``auto_scan_enabled`` is set true with no active
            resume present. Invalid field values are rejected as 422 by the schema.
   """
    if payload.auto_scan_enabled and await load_active_resume(db) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=NO_ACTIVE_RESUME_SCAN_MESSAGE,
        )

    updated = await store.update_scan_settings(
        auto_scan_enabled=payload.auto_scan_enabled,
        scan_frequency_hours=payload.scan_frequency_hours,
        notification_score_threshold=payload.notification_score_threshold,
    )
    logger.info(
        "Scan settings updated",
        extra={
            "auto_scan_enabled": updated["auto_scan_enabled"],
            "scan_frequency_hours": updated["scan_frequency_hours"],
        },
    )
    return ScanSettings(**updated)
