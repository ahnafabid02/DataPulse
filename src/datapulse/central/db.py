"""Connection lifecycle; migrations are a separate operational step."""

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from datapulse.central.config import Settings

EXPECTED_REVISION = "0002_access"


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=3,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
    )


def database_ready(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            revisions = connection.execute(text("SELECT version_num FROM alembic_version"))
            return set(revisions.scalars()) == {EXPECTED_REVISION}
    except SQLAlchemyError:
        # Do not log exceptions that can contain connection strings or SQL values.
        return False
