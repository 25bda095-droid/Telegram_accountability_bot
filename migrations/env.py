"""
migrations/env.py — Alembic async migration environment.

Supports both online (with DB connection) and offline (SQL script) modes.
Uses SQLAlchemy async engine to work with aiosqlite (dev) and asyncpg (prod).
The database URL is always read from config.py / .env so there is a single
source of truth; the value in alembic.ini is only a fallback for tooling
that reads the ini directly (e.g. IDE plugins).
"""

import asyncio
import logging
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Load the application's ORM metadata so Alembic can diff against it.
# ---------------------------------------------------------------------------
# Import Base and all models so that Base.metadata is fully populated.
from models.db_models import Base  # noqa: F401 — side-effect import registers all tables
import models.db_models  # noqa: F401

# Import settings so we can override the URL from the environment.
from config import settings

# ---------------------------------------------------------------------------
# Alembic Config object (gives access to values in alembic.ini)
# ---------------------------------------------------------------------------
config = context.config

# Override the sqlalchemy.url with the value from pydantic-settings / .env.
# This is the authoritative source; alembic.ini is only a fallback.
config.set_main_option("sqlalchemy.url", settings.database_url)

# ---------------------------------------------------------------------------
# Logging — interpret the config file's logging section if present.
# ---------------------------------------------------------------------------
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# Target metadata for --autogenerate support.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def include_object(object, name, type_, reflected, compare_to):  # noqa: A002
    """
    Control which objects Alembic compares during autogenerate.
    Return False to exclude an object from the diff.
    """
    # Skip SQLite internal tables
    if type_ == "table" and name.startswith("sqlite_"):
        return False
    return True


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an actual DB
    connection, so no DBAPI is required.  Calls to context.execute() emit
    the generated SQL to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations inside a synchronous connection context (called from async)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        # Render item-level batch mode for SQLite ALTER TABLE compatibility.
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode using an async engine.

    Creates a connection from the async engine, then hands control to the
    synchronous ``do_run_migrations`` helper via ``run_sync``.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online mode — runs the async coroutine."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    logger.info("Running migrations in offline mode")
    run_migrations_offline()
else:
    logger.info("Running migrations in online mode")
    run_migrations_online()