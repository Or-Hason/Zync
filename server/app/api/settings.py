"""Settings API facade.

This file forwards imports to the refactored `app.api.settings_routes.router` package
to maintain backward compatibility with existing imports across the codebase.
"""

from app.api.settings_routes.router import router

__all__ = ["router"]
