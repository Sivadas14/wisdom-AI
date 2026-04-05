import asyncio
import ssl
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from alembic import context

from src.db import meta
from src.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = meta


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the same SSL config as the main app."""
    # Build the same SSL context the main app uses so migrations can reach Supabase
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE  # Supabase self-signed cert; disable verification

    connectable = create_async_engine(
        str(settings.db_url),
        connect_args={"ssl": ssl_context},
    )
    if isinstance(connectable, AsyncEngine):
        asyncio.run(run_async_migrations(connectable))
    else:
        do_run_migrations(connectable)


async def run_async_migrations(connectable):
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
