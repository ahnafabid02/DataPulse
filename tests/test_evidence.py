"""Evidence limits, scope, snapshot semantics, join ambiguity and immutable audit."""

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import sqlalchemy as sa

from datapulse.connectors.connection import ConnectionConfig
from datapulse.connectors.evidence import (
    EvidenceError,
    EvidencePolicy,
    EvidenceRequest,
    MySQLEvidenceReader,
    ProfileSelection,
    RelationshipSelection,
)
from datapulse.contracts.schema import ColumnSchema, DatabaseSchema, TableRef, TableSchema
from datapulse.hospital.__main__ import main
from datapulse.hospital.registry import HospitalRegistry, RegistryError, migrate_registry


def setup_reader(
    monkeypatch, *, duplicate=0, unmatched=0, too_many=False, engine="InnoDB", oversized=False
):
    source = uuid4()
    table = TableRef(namespace="fixture", name="patient`records")
    child = TableRef(namespace="fixture", name="visits")
    columns = (
        ColumnSchema(
            name="id", ordinal=1, native_type="int", normalized_type="integer", nullable=False
        ),
        ColumnSchema(
            name="label",
            ordinal=2,
            native_type="varchar(50)",
            normalized_type="string",
            nullable=True,
        ),
    )
    schema = DatabaseSchema(
        source_system_id=source,
        database_name="fixture",
        vendor="mariadb",
        scanned_at=datetime.now(UTC),
        tables=(
            TableSchema(**table.model_dump(), columns=columns, primary_key=("id",)),
            TableSchema(**child.model_dump(), columns=columns, primary_key=("id",)),
        ),
    )
    config = ConnectionConfig(
        source_system_id=source,
        vendor="mariadb",
        host="127.0.0.1",
        database="fixture",
        credential_ref="fixture/key",
        tls_mode="disabled_local_demo",
    )
    reader = MySQLEvidenceReader(config, MagicMock())
    monkeypatch.setattr(reader._scanner, "introspect", lambda _: schema)
    connection = MagicMock()
    executed = []

    def cursor_factory():
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor

        def execute(sql, args=()):
            executed.append((sql, args))
            if "SELECT ENGINE" in sql:
                rows = [(engine,)]
            elif sql.startswith("SELECT 1 FROM"):
                rows = [(1,)] * (3 if too_many else 2)
            elif "SELECT LEFT" in sql:
                rows = [(b"1", b"A" * 257 if oversized else b"Fictional"), (b"2", None)]
            elif "NOT EXISTS" in sql:
                rows = [(unmatched,)]
            elif "GROUP BY" in sql:
                rows = [(duplicate,)]
            elif "SELECT COUNT" in sql:
                rows = [(0,)]
            else:
                rows = []
            cursor.fetchall.return_value = rows

        cursor.execute.side_effect = execute
        return cursor

    connection.cursor.side_effect = cursor_factory

    @contextmanager
    def open_readonly():
        yield connection

    monkeypatch.setattr(reader._probe, "open_readonly", open_readonly)
    request = EvidenceRequest(
        source_system_id=source,
        schema_fingerprint=schema.structural_fingerprint(),
        profiles=(ProfileSelection(table=table, columns=("id", "label")),),
        relationships=(
            RelationshipSelection(
                source_table=child,
                source_columns=("id",),
                target_table=table,
                target_columns=("id",),
            ),
        ),
        policy=EvidencePolicy(max_check_rows=2),
    )
    return reader, schema, request, connection, executed


def test_profiles_preserve_nulls_and_join_metrics_never_authorize(monkeypatch):
    reader, schema, request, connection, executed = setup_reader(monkeypatch)
    observed = reader.capture(request, schema)
    assert observed.profiles[0].distinct_values == (1, 2)
    assert observed.profiles[1].null_count == 1
    join = observed.relationships[0]
    assert join.complete and join.status == "needs_review" and join.approved is False
    assert join.unmatched_source_rows == 0 and join.target_duplicate_key_groups == 0
    assert any("`patient``records`" in sql for sql, _ in executed)
    assert ("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY", ()) in executed
    assert all("LEFT(CAST(" in sql for sql, _ in executed if sql.startswith("SELECT LEFT"))
    connection.rollback.assert_called_once()


@pytest.mark.parametrize("options", [{"duplicate": 1}, {"unmatched": 1}])
def test_duplicate_or_unmatched_keys_contradict_candidate(monkeypatch, options):
    reader, schema, request, _, _ = setup_reader(monkeypatch, **options)
    assert reader.capture(request, schema).relationships[0].status == "contradicted"


def test_row_limit_is_incomplete_without_aggregating_whole_database(monkeypatch):
    reader, schema, request, _, executed = setup_reader(monkeypatch, too_many=True)
    join = reader.capture(request, schema).relationships[0]
    assert not join.complete and join.status == "incomplete"
    assert join.unmatched_source_rows is None and join.target_duplicate_key_groups is None
    assert not any("COUNT(*)" in sql for sql, _ in executed)


@pytest.mark.parametrize(
    "options,category",
    [
        ({"engine": "MyISAM"}, "unsupported_snapshot_engine"),
        ({"oversized": True}, "value_limit_exceeded"),
    ],
)
def test_snapshot_and_value_limits_fail_closed(monkeypatch, options, category):
    reader, schema, request, _, _ = setup_reader(monkeypatch, **options)
    with pytest.raises(EvidenceError, match=category):
        reader.capture(request, schema)


def test_source_scope_structural_drift_and_deadline_guards(monkeypatch):
    reader, schema, request, _, _ = setup_reader(monkeypatch)
    with pytest.raises(EvidenceError, match="source_mismatch"):
        reader.capture(request.model_copy(update={"source_system_id": uuid4()}), schema)
    invalid = ProfileSelection(table=request.profiles[0].table, columns=("not_present",))
    with pytest.raises(EvidenceError, match="scope_unavailable"):
        reader.capture(request.model_copy(update={"profiles": (invalid,)}), schema)
    changed = schema.model_copy(update={"tables": ()})
    monkeypatch.setattr(reader._scanner, "introspect", lambda _: changed)
    with pytest.raises(EvidenceError, match="schema_changed"):
        reader.capture(request, schema)
    monkeypatch.setattr(reader._scanner, "introspect", lambda _: schema)
    ticks = iter((0, 61))
    monkeypatch.setattr("datapulse.connectors.evidence.time.monotonic", lambda: next(ticks))
    with pytest.raises(EvidenceError, match="timeout"):
        reader.capture(request, schema)


def test_access_audit_precedes_read_and_observation_survives_reopen(monkeypatch, tmp_path):
    reader, schema, request, _, _ = setup_reader(monkeypatch)
    path = tmp_path / "hospital.sqlite"
    migrate_registry(path)
    registry = HospitalRegistry(path)
    receipt = registry.save_scan(schema)
    access = registry.begin_evidence_access(receipt.scan_id, request, "demo-reviewer")
    with sa.create_engine(sa.URL.create("sqlite", database=str(path))).connect() as db:
        assert db.exec_driver_sql("SELECT phase FROM evidence_access").scalar() == "started"
    observed = reader.capture(request, schema)
    registry.finish_evidence_access(access, observed)
    registry.close()
    registry = HospitalRegistry(path)
    assert registry.load_evidence(observed.observation_id, schema.source_system_id) == observed
    with pytest.raises(RegistryError, match="evidence_unavailable"):
        registry.load_evidence(observed.observation_id, uuid4())
    with pytest.raises(RegistryError, match="access_unavailable"):
        registry.finish_evidence_access(access, observed)
    engine = sa.create_engine(sa.URL.create("sqlite", database=str(path)))
    with engine.begin() as db:
        for table in ("evidence_access", "evidence_observations"):
            with pytest.raises(sa.exc.DatabaseError):
                db.exec_driver_sql(f"DELETE FROM {table}")
            with pytest.raises(sa.exc.DatabaseError):
                db.exec_driver_sql(f"UPDATE {table} SET source_id='changed'")
    registry.close()
    engine.dispose()


def test_failed_read_audit_redacts_untrusted_errors_and_rejects_forged_request(
    monkeypatch, tmp_path
):
    reader, schema, request, _, _ = setup_reader(monkeypatch)
    path = tmp_path / "hospital.sqlite"
    migrate_registry(path)
    registry = HospitalRegistry(path)
    receipt = registry.save_scan(schema)
    access = registry.begin_evidence_access(receipt.scan_id, request, "reviewer")
    observed = reader.capture(request, schema)
    altered = observed.model_copy(
        update={"request": request.model_copy(update={"relationships": ()})}
    )
    with pytest.raises(RegistryError, match="evidence_identity_mismatch"):
        registry.finish_evidence_access(access, altered)
    registry.finish_evidence_access(access, None, "secret from driver")
    with registry._engine.connect() as db:
        rows = db.exec_driver_sql("SELECT phase,category FROM evidence_access").fetchall()
        assert rows == [("started", None), ("failed", "evidence_unavailable")]
    registry.close()


def test_cli_does_not_echo_invalid_submitted_values(capsys):
    assert main(["capture", "--password", "never-print-this-secret"]) == 1
    output = capsys.readouterr().out
    assert "never-print" not in output and json.loads(output)["error"] == "evidence_unavailable"


def test_quoted_identifiers_preserve_literal_percent_through_driver_interpolation():
    from datapulse.connectors.evidence import _quote

    sql = f"SELECT {_quote('literal%s`name')} LIMIT %s"
    assert sql % (3,) == "SELECT `literal%s``name` LIMIT 3"


def test_sample_truncation_and_serialized_byte_bound(monkeypatch):
    reader, schema, request, _, _ = setup_reader(monkeypatch)
    small = request.model_copy(update={"policy": EvidencePolicy(max_sample_rows=1)})
    observed = reader.capture(small, schema)
    assert all(p.sample_count == 1 and p.truncated for p in observed.profiles)
    tiny = request.model_copy(update={"policy": EvidencePolicy(max_evidence_bytes=1024)})
    with pytest.raises(EvidenceError, match="limit_exceeded"):
        reader.capture(tiny, schema)


def test_composite_checks_keep_key_order_and_null_semantics(monkeypatch):
    reader, schema, request, _, executed = setup_reader(monkeypatch)
    relation = request.relationships[0].model_copy(
        update={"source_columns": ("id", "label"), "target_columns": ("id", "label")}
    )
    observed = reader.capture(request.model_copy(update={"relationships": (relation,)}), schema)
    assert observed.relationships[0].complete
    queries = [sql for sql, _ in executed]
    assert any("GROUP BY `id`,`label`" in sql for sql in queries)
    assert any("`id` IS NULL OR `label` IS NULL" in sql for sql in queries)
    assert any("s.`id`=t.`id` AND s.`label`=t.`label`" in sql for sql in queries)


def test_drift_after_snapshot_rejects_observation(monkeypatch):
    reader, schema, request, _, _ = setup_reader(monkeypatch)
    scans = iter((schema, schema.model_copy(update={"tables": ()})))
    monkeypatch.setattr(reader._scanner, "introspect", lambda _: next(scans))
    with pytest.raises(EvidenceError, match="schema_changed"):
        reader.capture(request, schema)


def test_hospital_migration_preserves_m4_rows_and_guards_old_head(monkeypatch, tmp_path):
    _, schema, request, _, _ = setup_reader(monkeypatch)
    path = tmp_path / "registry.sqlite"
    migrate_registry(path, "hospital_0002")
    with pytest.raises(RegistryError, match="revision_mismatch"):
        HospitalRegistry(path)
    migrate_registry(path)
    registry = HospitalRegistry(path)
    scan = registry.save_scan(schema)
    registry.begin_evidence_access(scan.scan_id, request, "reviewer")
    registry.close()

    from alembic import command
    from alembic.config import Config

    import datapulse.hospital.registry as module

    config = Config()
    config.set_main_option("script_location", str(Path(module.__file__).parent / "migrations"))
    engine = sa.create_engine(sa.URL.create("sqlite", database=str(path)))
    with engine.begin() as db:
        config.attributes["connection"] = db
        command.downgrade(config, "hospital_0002")
        assert "evidence_access" not in sa.inspect(db).get_table_names()
        assert db.exec_driver_sql("SELECT COUNT(*) FROM schema_scans").scalar() == 1
    engine.dispose()
    migrate_registry(path)
    registry = HospitalRegistry(path)
    assert registry.load_scan(scan.scan_id, schema.source_system_id) == schema
    registry.close()


def test_inventory_keeps_every_column_including_unknown_domains(monkeypatch, tmp_path, capsys):
    from datapulse.hospital.coverage import inventory

    _, schema, _, _, _ = setup_reader(monkeypatch)
    result = inventory(schema)
    assert len(result.fields) == sum(len(t.columns) for t in schema.tables)
    assert all(f.status == "unresolved" for f in result.fields)
    assert result.complete_clinical_mapping is False
    path = tmp_path / "registry.sqlite"
    migrate_registry(path)
    registry = HospitalRegistry(path)
    scan = registry.save_scan(schema)
    registry.close()
    output = tmp_path / "coverage.json"
    assert (
        main(
            [
                "inventory",
                "--registry",
                str(path),
                "--scan-id",
                str(scan.scan_id),
                "--source-id",
                str(schema.source_system_id),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text())["fields"] == result.model_dump(mode="json")["fields"]
    assert json.loads(capsys.readouterr().out)["fields"] == 4
