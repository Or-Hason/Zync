"""Base operations for the settings singleton row."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import DEFAULT_SETTINGS_DATA, SETTINGS_ROW_ID, Settings

class BaseSettingsStore:
    """Base store providing read/write access to the singleton settings row."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the store.
        Args:
            db: The active async DB session.
        """
        self._db = db

    async def _load(self) -> dict:
        """Return the settings blob, creating the default row if absent."""
        ensure = (
            insert(Settings)
            .values(id=SETTINGS_ROW_ID, data=dict(DEFAULT_SETTINGS_DATA))
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self._db.execute(ensure)
        result = await self._db.execute(
            select(Settings.data).where(Settings.id == SETTINGS_ROW_ID)
        )
        return dict(result.scalar_one())

    async def _save(self, data: dict) -> None:
        """Persist the full settings blob via a race-safe upsert."""
        stmt = (
            insert(Settings)
            .values(id=SETTINGS_ROW_ID, data=data)
            .on_conflict_do_update(index_elements=["id"], set_={"data": data})
        )
        await self._db.execute(stmt)
