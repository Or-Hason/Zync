import asyncio
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.models.base import Base

# Ensure all models are imported so their tables are registered on Base.metadata.
import app.models  # noqa: F401

alembic_config = context.config
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata
logger = logging.getLogger("alembic")
settings = get_settings()


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (outputs SQL only)."""
    context.configure(
        url=settings.alembic_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live async DB connection."""
    engine = create_async_engine(settings.database_url, echo=False)
    logger.info("Running migrations against %s", settings.database_url_masked)
    async with engine.connect() as conn:
        await conn.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
