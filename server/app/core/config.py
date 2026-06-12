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

    # ── Gemini (cloud AI inference for match scoring) ─────────────────────────
    # Loaded from the environment; never hardcoded or logged. Empty when unset,
    # in which case the scoring endpoint aborts with HTTP 500.
    gemini_api_key: str = ""
    # Comma-separated ordered list of model IDs. The fallback engine cycles
    # through them on 429 errors and resets to the primary after 1 hour.
    gemini_models: str = ""
    gemini_timeout_seconds: float = 30.0

    @property
    def gemini_models_list(self) -> list[str]:
        """Ordered list of Gemini model IDs parsed from GEMINI_MODELS."""
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]

    # ── Background scraper (JobMaster auto-scan) ──────────────────────────────
    # Base site URL; the search URL is derived from it at runtime.
    jobmaster_base_url: str = "https://www.jobmaster.co.il/"
    # Hard cap on jobs processed on the very FIRST scan for this source, so the
    # initial import never burns a large number of Gemini calls at once.
    initial_scan_limit: int = 3
    # Defensive ceiling on jobs processed per scheduler tick on ANY run (incl.
    # subsequent ones). Guards against a portal returning hundreds of new links
    # in one cycle and triggering uncontrolled API usage.
    max_jobs_per_scan: int = 4
    # Master switch for the background scheduler. Disabled in test runs so the
    # suite never spins up a real DB-hitting background loop.
    scheduler_enabled: bool = True

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
