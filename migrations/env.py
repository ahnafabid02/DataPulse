"""Migration URL from settings, or explicit programmatic test connection."""

from alembic import context

from datapulse.central.config import Settings
from datapulse.central.db import build_engine
from datapulse.central.models import Base

config = context.config


def run_migrations() -> None:
    if context.is_offline_mode():
        settings = Settings()
        context.configure(
            url=settings.database_url.get_secret_value(),
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = build_engine(Settings())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=Base.metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
