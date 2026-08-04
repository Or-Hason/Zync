"""Facade wrapper for the settings store.

This file forwards imports to the refactored `app.services.settings` package
to maintain backward compatibility with existing imports across the codebase.
"""

from app.services.settings.store import (
    SettingsStore,
    get_settings_store,
    DuplicateKeywordError,
)

__all__ = ["SettingsStore", "get_settings_store", "DuplicateKeywordError"]
