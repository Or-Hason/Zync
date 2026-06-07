from __future__ import annotations

from sqlalchemy import CheckConstraint, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Fixed primary key for the one-and-only settings row (singleton table).
SETTINGS_ROW_ID = 1

# Default JSONB payload created on first access.
DEFAULT_SETTINGS_DATA: dict = {
    "blacklist": [],
    "blacklist_bypass_preference": "ask",
}


class Settings(Base):
    """Singleton row holding all user settings as a flexible JSONB blob.

    A ``CHECK (id = 1)`` constraint enforces that only one row can ever exist,
    so reads and writes always target the same record via upsert.
    """

    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint(f"id = {SETTINGS_ROW_ID}", name="ck_settings_singleton"),
    )

    id: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, autoincrement=False, default=SETTINGS_ROW_ID
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
