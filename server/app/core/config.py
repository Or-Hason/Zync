from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ──────────────────────────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "zync_user"
    db_password: str = "zync_password"
    db_name: str = "zync_db"

    # ── Application ───────────────────────────────────────────────────────────
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # ── Ollama (local AI inference) ───────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b"
    ollama_timeout_seconds: float = 120.0

    # ── Resume uploads ────────────────────────────────────────────────────────
    # Directory (relative paths are resolved against the server working dir).
    upload_dir: str = "uploads"
    # Hard cap on accepted upload size; larger files are rejected with HTTP 413.
    max_upload_size_mb: int = 10

    @property
    def upload_path(self) -> Path:
        """Absolute path to the uploads directory (created on demand)."""
        return Path(self.upload_dir).resolve()

    @property
    def max_upload_size_bytes(self) -> int:
        """Upload size cap expressed in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection string."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_masked(self) -> str:
        """Connection string safe for logging — password replaced with ***."""
        return (
            f"postgresql+asyncpg://{self.db_user}:***"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def alembic_url(self) -> str:
        """Sync connection string used by Alembic offline mode."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
