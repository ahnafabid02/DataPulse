"""Real read-only acceptance against the fixed empty or recognized fictional EHRs."""

import os
from pathlib import Path

import certifi
import pymysql
import pytest

from datapulse.connectors.connection import (
    ConnectionConfig,
    FileCredentialResolver,
    ResolvedCredential,
)
from datapulse.connectors.introspection import MySQLSchemaScanner, ScanError, ScanPolicy
from datapulse.connectors.mysql import MySQLConnectionProbe
from datapulse.hospital.registry import HospitalRegistry, migrate_registry

SOURCES = (
    ("openmrs", 13306, "0385fb0c-b004-4a57-9523-9e53fb9af033", "10.11.7", "patient", "patient_id"),
    ("openemr", 13307, "aa5874e0-0482-4621-805d-afb2ad244cd4", "12.3.3", "patient_data", "id"),
)


@pytest.mark.source_db
@pytest.mark.parametrize("source,port,source_id,version,table,key", SOURCES)
def test_actual_metadata_scan_repeat_persistence_and_limits(
    source, port, source_id, version, table, key, tmp_path
):
    location = os.environ.get("DATAPULSE_DEMO_TEST_DIR")
    if not location:
        pytest.skip("Set DATAPULSE_DEMO_TEST_DIR for the two accepted fictional sources")
    local = Path(location)
    config = ConnectionConfig.model_validate_json((local / f"{source}.json").read_bytes())
    assert (config.host, config.port, str(config.source_system_id), config.database) == (
        "127.0.0.1",
        port,
        source_id,
        source,
    )
    resolver = FileCredentialResolver(local / "credentials.json")
    scanner = MySQLSchemaScanner(config, resolver, ScanPolicy())
    first, second = (
        scanner.introspect(config.source_system_id),
        scanner.introspect(config.source_system_id),
    )
    assert first.tables and first.structural_fingerprint() == second.structural_fingerprint()
    assert table in {t.name for t in first.tables}
    assert any(t.primary_key for t in first.tables)
    if source == "openmrs":
        assert any(t.foreign_keys for t in first.tables)
    assert all(not t.relationship_hints for t in first.tables)
    path = tmp_path / "hospital.sqlite"
    migrate_registry(path)
    registry = HospitalRegistry(path)
    a, b = registry.save_scan(first), registry.save_scan(second)
    registry.close()
    registry = HospitalRegistry(path)
    assert registry.load_scan(a.scan_id, config.source_system_id) == first
    assert registry.load_scan(b.scan_id, config.source_system_id) == second
    registry.close()
    with pytest.raises(ScanError, match="limit_exceeded"):
        MySQLSchemaScanner(config, resolver, ScanPolicy(max_tables=1)).introspect(
            config.source_system_id
        )


@pytest.mark.source_db
@pytest.mark.parametrize("source,port,source_id,version,table,key", SOURCES)
def test_pinned_source_connection_health_and_real_denials(
    source, port, source_id, version, table, key
):
    location = os.environ.get("DATAPULSE_DEMO_TEST_DIR")
    if not location:
        pytest.skip("Set DATAPULSE_DEMO_TEST_DIR to the accepted fixed fictional EHR configs")
    local = Path(location)
    config = ConnectionConfig.model_validate_json((local / f"{source}.json").read_bytes())
    assert (config.host, config.port, str(config.source_system_id), config.database) == (
        "127.0.0.1",
        port,
        source_id,
        source,
    ), "Refusing a different source environment"
    resolver = FileCredentialResolver(local / "credentials.json")
    credential = resolver.resolve(config.credential_ref)
    probe = MySQLConnectionProbe(config, resolver)
    report = probe.check()
    assert report.status == "healthy", report.model_dump_json()
    secret = credential.password.get_secret_value()
    assert secret not in report.model_dump_json()
    with pymysql.connect(
        host=config.host,
        port=port,
        database=source,
        user=credential.username.get_secret_value(),
        password=secret,
        connect_timeout=3,
        read_timeout=3,
        write_timeout=3,
        ssl_disabled=True,
    ) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            assert cursor.fetchone()[0].startswith(version)
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            if count != 0:
                import sys

                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra/demo"))
                from seed_clinical import verify_seed

                assert count == 3 and verify_seed(source), "Refusing unrecognized clinical data"
            # Zero-row DML cannot alter records even if permission regresses.
            denied = (
                f"UPDATE `{table}` SET `{key}`=`{key}` WHERE 1=0",
                f"DELETE FROM `{table}` WHERE 1=0",
                f"INSERT INTO `{table}` (`{key}`) SELECT -1 WHERE 1=0",
                "CREATE TEMPORARY TABLE datapulse_permission_probe (id INTEGER)",
            )
            for sql in denied:
                with pytest.raises(pymysql.err.DatabaseError) as error:
                    cursor.execute(sql)
                assert error.value.args[0] in (1044, 1142)
            with pytest.raises(pymysql.err.DatabaseError) as error:
                cursor.execute("SELECT COUNT(*) FROM mysql.user")
            assert error.value.args[0] in (1044, 1142)
            db.rollback()
    wrong = ResolvedCredential(
        source_system_id=config.source_system_id,
        username=credential.username,
        password="intentionally-incorrect",
    )

    class WrongCredential:
        def resolve(self, reference):
            return wrong

    assert (
        MySQLConnectionProbe(config, WrongCredential()).check().failure == "authentication_failed"
    )
    alternate = "openemr" if source == "openmrs" else "openmrs"
    assert MySQLConnectionProbe(
        config.model_copy(update={"database": alternate}), resolver
    ).check().failure in (
        "database_denied",
        "database_unavailable",
    )
    tls = ConnectionConfig.model_validate(
        {**config.model_dump(), "tls_mode": "verify_identity", "ca_file": certifi.where()}
    )
    assert MySQLConnectionProbe(tls, resolver).check().failure == "tls_failed"
    assert (
        MySQLConnectionProbe(config.model_copy(update={"vendor": "mysql"}), resolver)
        .check()
        .failure
        == "vendor_mismatch"
    )
    # This dedicated local closed port is not an external system or a patient endpoint.
    unavailable = config.model_copy(update={"port": 1})
    assert MySQLConnectionProbe(unavailable, resolver).check().failure == "connection_unavailable"
