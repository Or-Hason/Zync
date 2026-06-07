"""Settings API: blacklist keyword management and bypass preference."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.settings import (
    BlacklistResponse,
    BypassPreferenceModel,
    KeywordRequest,
)
from app.services.settings_store import (
    DuplicateKeywordError,
    SettingsStore,
    get_settings_store,
)

router = APIRouter(prefix="/settings", tags=["settings"])
logger = logging.getLogger(__name__)


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
