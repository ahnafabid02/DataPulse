from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import migrate
from sqlalchemy import delete, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from datapulse.central.db import database_ready
from datapulse.central.models import Base, Organization, SourceSystem


def make_source(organization_id, **overrides):
    values = {
        "organization_id": organization_id,
        "code": "ehr-primary",
        "ehr_product": "Synthetic EHR",
        "database_vendor": "mysql",
        "database_name": "controlled_demo",
    }
    values.update(overrides)
    return SourceSystem(**values)


def assert_foundation_constraints(engine):
    with Session(engine) as session:
        first = Organization(code="hospital-a", name="Hospital A")
        second = Organization(code="hospital-b", name="Hospital B")
        session.add_all([first, second])
        session.flush()
        first_id, second_id = first.id, second.id
        session.add(make_source(first_id))
        session.commit()
        session.add(make_source(second_id))  # Same code at a different organization is valid.
        session.commit()
        session.add(make_source(first_id))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        for field, value in [
            ("database_vendor", "unsupported"),
            ("status", "invented"),
            ("database_name", " "),
            ("ehr_product", ""),
            ("code", " "),
        ]:
            session.add(make_source(first_id, **{"code": "different", field: value}))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        session.add(make_source(uuid4(), code="orphan"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        with pytest.raises(IntegrityError):
            session.execute(delete(Organization).where(Organization.id == first_id))
            session.commit()
        session.rollback()
        session.add(Organization(code="hospital-a", name="Duplicate"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(Organization(code=" ", name="Blank"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.execute(delete(SourceSystem))
        session.execute(delete(Organization))
        session.commit()


def test_migration_matches_orm_and_supports_constraints(migrated_engine):
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []
    assert_foundation_constraints(migrated_engine)
    assert database_ready(migrated_engine)
    migrate(migrated_engine, "base", downgrade=True)
    assert inspect(migrated_engine).get_table_names() == ["alembic_version"]
    assert not database_ready(migrated_engine)
    migrate(migrated_engine)
    assert database_ready(migrated_engine)
