"""Blacklist and bypass preference operations."""

from app.services.settings.base_store import BaseSettingsStore

class DuplicateKeywordError(Exception):
    """Raised when adding a blacklist keyword that already exists."""

class BlacklistMixin(BaseSettingsStore):
    """Mixin for blacklist and bypass preference settings."""

    async def get_blacklist(self) -> list[str]:
        """Return the current blacklist keywords."""
        data = await self._load()
        return list(data.get("blacklist", []))

    async def add_keyword(self, keyword: str) -> list[str]:
        """Add a trimmed, deduped keyword to the blacklist.

        Args:
            keyword: The keyword to add.

        Returns:
            The updated keyword list.

        Raises:
            ValueError: If the keyword is blank after trimming.
            DuplicateKeywordError: If the keyword already exists (case-insensitive).
        """
        cleaned = keyword.strip()
        if not cleaned:
            raise ValueError("Keyword must not be blank.")

        data = await self._load()
        keywords = list(data.get("blacklist", []))
        if any(cleaned.lower() == existing.lower() for existing in keywords):
            raise DuplicateKeywordError(cleaned)

        keywords.append(cleaned)
        data["blacklist"] = keywords
        await self._save(data)
        return keywords

    async def remove_keyword(self, keyword: str) -> list[str]:
        """Remove a keyword (case-insensitive) from the blacklist.

        Args:
            keyword: The keyword to remove.

        Returns:
            The updated keyword list.
        """
        target = keyword.strip().lower()
        data = await self._load()
        keywords = [k for k in data.get("blacklist", []) if k.lower() != target]
        data["blacklist"] = keywords
        await self._save(data)
        return keywords

    async def get_bypass_preference(self) -> str:
        """Return the blacklist-bypass preference (``ask``/``always``/``never``)."""
        data = await self._load()
        return data.get("blacklist_bypass_preference", "ask")

    async def set_bypass_preference(self, preference: str) -> None:
        """Persist the blacklist-bypass preference.

        Args:
            preference: One of ``ask``, ``always``, ``never``.
        """
        data = await self._load()
        data["blacklist_bypass_preference"] = preference
        await self._save(data)
