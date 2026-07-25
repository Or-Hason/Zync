"""Letter template operations."""

from app.services.settings.base_store import BaseSettingsStore

class TemplateMixin(BaseSettingsStore):
    """Mixin for letter template configurations."""

    async def get_letter_template(self) -> dict:
        """Return the letter template fields from the settings blob.

        Returns:
            Dict with keys ``letter_template_text`` (str | None) and
            ``letter_template_filename`` (str | None).
        """
        data = await self._load()
        return {
            "text": data.get("letter_template_text"),
            "filename": data.get("letter_template_filename"),
        }

    async def set_letter_template(self, text: str, filename: str) -> dict:
        """Persist the extracted letter template text and original filename.

        Args:
            text: Extracted plain text content of the uploaded file.
            filename: Original filename of the uploaded file.

        Returns:
            The saved template dict with ``text`` and ``filename`` keys.
        """
        data = await self._load()
        data["letter_template_text"] = text
        data["letter_template_filename"] = filename
        await self._save(data)
        return {"text": text, "filename": filename}

    async def update_letter_template_text(self, text: str) -> dict:
        """Update only the template text (inline editor save).

        Args:
            text: The edited template text.

        Returns:
            The updated template dict.
        """
        data = await self._load()
        data["letter_template_text"] = text
        await self._save(data)
        return {"text": text, "filename": data.get("letter_template_filename")}

    async def delete_letter_template(self) -> None:
        """Clear the letter template from the settings blob."""
        data = await self._load()
        data.pop("letter_template_text", None)
        data.pop("letter_template_filename", None)
        await self._save(data)
