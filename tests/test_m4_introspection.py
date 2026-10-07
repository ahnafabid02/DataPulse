"""Metadata-only adapter scope, lossless keys, consistency and bounded cleanup."""

from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from datapulse.connectors.connection import ConnectionConfig
from datapulse.connectors.introspection import MySQLSchemaScanner, ScanError, ScanPolicy
from datapulse.mapping.discovery import declared_graph


def scanner(monkeypatch, policy=None, changing=False):
    policy = policy or ScanPolicy()
    source = uuid4()
    config = ConnectionConfig(
        source_system_id=source,
        vendor="mariadb",
        host="127.0.0.1",
        database="fixture",
        credential_ref="fixture/key",
        tls_mode="disabled_local_demo",
    )
    connection = MagicMock()
    datasets = [
        [("CaseTable", "Declared metadata"), ("Target", "")],
        [
            ("CaseTable", "Second", 1, "int unsigned", "NO", None, "", 10, 0, None),
            ("CaseTable", "First", 2, "future_type", "YES", "NULL", "opaque", None, None, None),
            ("Target", "id", 1, "int", "NO", None, "", 10, 0, None),
        ],
        [
            ("CaseTable", "PRIMARY", "PRIMARY KEY", "First", 1, None, None, None),
            ("CaseTable", "PRIMARY", "PRIMARY KEY", "Second", 2, None, None, None),
            ("CaseTable", "fk_target", "FOREIGN KEY", "Second", 1, "fixture", "Target", "id"),
        ],
        [("CaseTable", "PRIMARY", "First", 0, 1), ("CaseTable", "PRIMARY", "Second", 0, 2)],
    ]
    observations = [*datasets, *datasets]
    if changing:
        observations[4] = [("CaseTable", "changed"), ("Target", "")]
    cursors = []
    for rows in observations:
        cursor = MagicMock()
        cursor.__iter__.return_value = iter(rows)
        cursors.append(cursor)
    connection.cursor.side_effect = cursors
    connection.open = True

    @contextmanager
    def open_connection():
        yield connection

    instance = MySQLSchemaScanner(config, MagicMock(), policy)
    monkeypatch.setattr(instance._probe, "open_readonly", open_connection)
    return instance, source, connection, cursors


def test_metadata_scan_preserves_case_composite_key_order_native_unknowns_and_external_fk(
    monkeypatch,
):
    instance, source, _, cursors = scanner(monkeypatch, ScanPolicy(tables=("CaseTable",)))
    scan = instance.introspect(source)
    assert len(scan.tables) == 1
    table = scan.tables[0]
    assert table.name == "CaseTable" and table.primary_key == ("First", "Second")
    assert table.columns[1].native_type == "future_type"
    assert table.columns[1].normalized_type == "unknown"
    assert table.columns[1].default == "NULL"
    assert table.foreign_keys[0].referenced_table.name == "Target"
    assert table.relationship_hints == ()
    assert declared_graph(scan)[0].target_in_scan is False
    for cursor in cursors:
        sql, parameters = cursor.execute.call_args.args
        assert "information_schema." in sql and parameters[0] == "fixture"
        assert "LIMIT %s" in sql and parameters[1] > 0
        assert "SELECT *" not in sql
        assert "TABLE_CONSTRAINTS" not in sql
        cursor.close.assert_called_once()
    assert "TABLE_TYPE='BASE TABLE'" in cursors[0].execute.call_args.args[0]


def test_scan_refuses_changed_metadata_missing_scope_and_wrong_source(monkeypatch):
    instance, source, _, _ = scanner(monkeypatch, changing=True)
    with pytest.raises(ScanError, match="schema_changed"):
        instance.introspect(source)
    instance, source, _, _ = scanner(monkeypatch, ScanPolicy(tables=("absent",)))
    with pytest.raises(ScanError, match="scope_unavailable"):
        instance.introspect(source)
    with pytest.raises(ScanError, match="source_mismatch"):
        instance.introspect(uuid4())


def test_oversized_metadata_closes_socket_before_stream_drain(monkeypatch):
    instance, source, connection, cursors = scanner(monkeypatch, ScanPolicy(max_tables=1))
    connection.close.side_effect = lambda: setattr(connection, "open", False)
    with pytest.raises(ScanError, match="limit_exceeded"):
        instance.introspect(source)
    connection.close.assert_called_once()
    cursors[0].close.assert_not_called()
    assert cursors[0].connection is None
    assert cursors[0]._result.unbuffered_active is False


def test_metadata_deadline_is_enforced(monkeypatch):
    instance, source, _, _ = scanner(monkeypatch, ScanPolicy(deadline_seconds=1))
    ticks = iter([0, 2])
    monkeypatch.setattr("datapulse.connectors.introspection.time.monotonic", lambda: next(ticks))
    with pytest.raises(ScanError, match="timeout"):
        instance.introspect(source)
