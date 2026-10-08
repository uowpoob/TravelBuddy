import asyncio

from alembic import context

from backend.app import models  # noqa: F401 -- register business tables
from backend.app.core.config import Settings
from backend.app.core.runtime import loop_factory
from backend.app.db.base import Base
from backend.app.db.session import create_engine

target_metadata = Base.metadata


def configure_and_run(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_name=lambda name, type_, parent_names: (
            name in target_metadata.tables if type_ == "table" else True
        ),
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    engine = create_engine(Settings())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(configure_and_run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        dialect_name="postgresql", target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online(), loop_factory=loop_factory)
