from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event

ROOT = Path(__file__).resolve().parents[1]


def migrate(engine: Engine, revision: str = "head", *, downgrade: bool = False) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        if downgrade:
            command.downgrade(config, revision)
        else:
            command.upgrade(config, revision)


@pytest.fixture
def empty_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", hide_parameters=True)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    yield engine
    engine.dispose()


@pytest.fixture
def migrated_engine(empty_engine: Engine) -> Engine:
    migrate(empty_engine)
    return empty_engine
