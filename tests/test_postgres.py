import os

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import migrate
from sqlalchemy import create_engine, inspect
from test_health import client_for
from test_migrations import assert_foundation_constraints

from datapulse.central.db import database_ready
from datapulse.central.models import Base


@pytest.mark.postgres
def test_postgres_foundation_lifecycle():
    url = os.environ.get("DATAPULSE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set DATAPULSE_TEST_DATABASE_URL to a disposable empty PostgreSQL database")
    engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 3})
    try:
        if engine.dialect.name != "postgresql":
            pytest.fail("PostgreSQL test requires PostgreSQL")
        if inspect(engine).get_table_names():
            pytest.fail("Refusing to migrate a nonempty test database")
        assert not database_ready(engine)
        migrate(engine)
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        assert_foundation_constraints(engine)
        with client_for(engine) as client:
            assert client.get("/health/ready").status_code == 200
        migrate(engine, "base", downgrade=True)
        assert not database_ready(engine)
        # This database was verified empty above and all application tables are gone.
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE alembic_version")
    finally:
        engine.dispose()
