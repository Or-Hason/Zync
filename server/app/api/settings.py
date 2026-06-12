"""Settings API: blacklist keyword management, bypass preference, and scan control."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.resumes_active import load_active_resume
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, get_db
from app.schemas.settings import (
    BlacklistResponse,
    BypassPreferenceModel,
    KeywordRequest,
    ScanSettings,
)
from app.scraper.jobmaster import run_scan
from app.services.gemini_client import get_gemini_client
from app.services.ollama_client import get_ollama_client
from app.services.settings_store import (
    DuplicateKeywordError,
    SettingsStore,
    get_settings_store,
)

router = APIRouter(prefix="/settings", tags=["settings"])
logger = logging.getLogger(__name__)

NO_ACTIVE_RESUME_SCAN_MESSAGE = (
    "An active resume is required to enable auto-scanning. "
    "Please upload or select a resume first."
)


@router.get(
    "/blacklist",
    response_model=BlacklistResponse,
    summary="List blacklist keywords",
)
async def get_blacklist(
    store: SettingsStore = Depends(get_settings_store),
) -> BlacklistResponse:
    """Return the current blacklist keyword list."""
    return BlacklistResponse(keywords=await store.get_blacklist())


@router.post(
    "/blacklist",
    response_model=BlacklistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a blacklist keyword",
)
async def add_blacklist_keyword(
    payload: KeywordRequest,
    store: SettingsStore = Depends(get_settings_store),
) -> BlacklistResponse:
    """Add a keyword to the blacklist.

    Raises:
        HTTPException: 409 if the keyword already exists; 422 if blank.
    """
    try:
        keywords = await store.add_keyword(payload.keyword)
    except DuplicateKeywordError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Keyword already exists in the blacklist.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Keyword must not be blank.",
        ) from exc
    return BlacklistResponse(keywords=keywords)


@router.delete(
    "/blacklist/{keyword}",
    response_model=BlacklistResponse,
    summary="Remove a blacklist keyword",
)
async def remove_blacklist_keyword(
    keyword: str,
    store: SettingsStore = Depends(get_settings_store),
) -> BlacklistResponse:
    """Remove a keyword from the blacklist (no-op if absent)."""
    return BlacklistResponse(keywords=await store.remove_keyword(keyword))


@router.get(
    "/blacklist-bypass-preference",
    response_model=BypassPreferenceModel,
    summary="Get the blacklist-bypass preference",
)
async def get_bypass_preference(
    store: SettingsStore = Depends(get_settings_store),
) -> BypassPreferenceModel:
    """Return the persisted blacklist-bypass preference."""
    return BypassPreferenceModel(preference=await store.get_bypass_preference())


@router.put(
    "/blacklist-bypass-preference",
    response_model=BypassPreferenceModel,
    summary="Set the blacklist-bypass preference",
)
async def set_bypass_preference(
    payload: BypassPreferenceModel,
    store: SettingsStore = Depends(get_settings_store),
) -> BypassPreferenceModel:
    """Persist the blacklist-bypass preference."""
    await store.set_bypass_preference(payload.preference)
    return payload


async def _run_manual_scan() -> None:
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
                notification_threshold=scan_cfg["notification_score_threshold"],
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
    asyncio.create_task(_run_manual_scan())
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
    """Return the persisted auto-scan configuration (defaults on first access)."""
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
