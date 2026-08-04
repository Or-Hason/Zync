"""Aggregated settings store."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.settings.base_store import BaseSettingsStore
from app.services.settings.blacklist_store import BlacklistMixin, DuplicateKeywordError
from app.services.settings.scan_store import ScanMixin
from app.services.settings.notification_store import NotificationMixin
from app.services.settings.template_store import TemplateMixin

class SettingsStore(
    BlacklistMixin,
    ScanMixin,
    NotificationMixin,
    TemplateMixin,
):
    """Facade for all settings."""

def get_settings_store(db: AsyncSession = Depends(get_db)) -> SettingsStore:
    """FastAPI dependency providing a :class:`SettingsStore` for the request."""
    return SettingsStore(db)

__all__ = ["SettingsStore", "get_settings_store", "DuplicateKeywordError"]
