import json
import ssl
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pymysql
import pytest
from pydantic import ValidationError
from pymysql.constants import CLIENT

from datapulse.connectors.__main__ import main
from datapulse.connectors.connection import (
    ConnectionConfig,
    ConnectionHealth,
    CredentialUnavailable,
    FileCredentialResolver,
    ResolvedCredential,
)
from datapulse.connectors.mysql import MySQLConnectionProbe, _TLSGuardConnection

SOURCE = UUID("0385fb0c-b004-4a57-9523-9e53fb9af033")
SECRET = "private-password-never-output"


def config(**changes):
    return ConnectionConfig.model_validate(
        {
            "source_system_id": str(SOURCE),
            "vendor": "mariadb",
            "host": "127.0.0.1",
            "database": "fixture",
            "credential_ref": "source/key",
            "tls_mode": "disabled_local_demo",
            **changes,
        }
    )


def credential(source_id=SOURCE):
    return ResolvedCredential(source_system_id=source_id, username="local_reader", password=SECRET)


def driver(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("fixture", "10.11.7-MariaDB", 1)
    cursor.fetchall.return_value = (
        ("GRANT USAGE ON *.* TO `local_reader`@`%`",),
        ("GRANT SELECT ON `fixture`.* TO `local_reader`@`%`",),
    )
    factory = MagicMock(return_value=connection)
    monkeypatch.setattr("datapulse.connectors.mysql._TLSGuardConnection", factory)
    resolver = MagicMock()
    resolver.resolve.return_value = credential()
    return connection, cursor, factory, resolver


def test_health_authenticates_checks_database_permissions_and_closes(monkeypatch):
    connection, cursor, factory, resolver = driver(monkeypatch)
    report = MySQLConnectionProbe(config(), resolver).check()
    assert report.status == "healthy" and report.failure is None
    assert report.source_system_id == SOURCE and report.checked_at.utcoffset().total_seconds() == 0
    assert SECRET not in report.model_dump_json()
    kwargs = factory.call_args.kwargs
    assert kwargs["local_infile"] is False
    assert kwargs["defer_connect"] is True and kwargs["ssl_disabled"] is True
    assert kwargs["connect_timeout"] == kwargs["read_timeout"] == kwargs["write_timeout"] == 3
    connection.connect.assert_called_once()
    cursor.execute.assert_any_call("SHOW GRANTS FOR CURRENT_USER()")
    connection.cursor.return_value.__exit__.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    "grant",
    [
        "GRANT ALL PRIVILEGES ON `fixture`.* TO `local_reader`@`%`",
        "GRANT SELECT ON *.* TO `local_reader`@`%`",
        "GRANT SELECT ON `another`.* TO `local_reader`@`%`",
        "GRANT SELECT ON `fixture`.* TO `local_reader`@`%` WITH GRANT OPTION",
        "GRANT `writer_role` TO `local_reader`@`%`",
        "GRANT SELECT, UPDATE ON `fixture`.* TO `local_reader`@`%`",
    ],
)
def test_excessive_cross_database_or_delegated_access_is_not_healthy(monkeypatch, grant):
    connection, cursor, _, resolver = driver(monkeypatch)
    cursor.fetchall.return_value += ((grant,),)
    report = MySQLConnectionProbe(config(), resolver).check()
    assert report.failure == "unsafe_privileges"
    connection.close.assert_called_once()


def test_usage_alone_is_insufficient_and_wrong_database_vendor_are_detected(monkeypatch):
    _, cursor, _, resolver = driver(monkeypatch)
    cursor.fetchall.return_value = (("GRANT USAGE ON *.* TO `local_reader`@`%`",),)
    assert MySQLConnectionProbe(config(), resolver).check().failure == "unsafe_privileges"
    cursor.fetchone.return_value = ("other_db", "10.11.7-MariaDB", 1)
    assert MySQLConnectionProbe(config(), resolver).check().failure == "database_unavailable"
    cursor.fetchone.return_value = ("fixture", "8.4.0", 1)
    assert MySQLConnectionProbe(config(), resolver).check().failure == "vendor_mismatch"
    cursor.fetchone.return_value = ("fixture", None, 1)
    assert MySQLConnectionProbe(config(), resolver).check().failure == "database_unavailable"


@pytest.mark.parametrize(
    "error,category",
    [
        (pymysql.err.OperationalError(1045, SECRET), "authentication_failed"),
        (pymysql.err.OperationalError(1044, SECRET), "database_denied"),
        (pymysql.err.OperationalError(1049, SECRET), "database_unavailable"),
        (pymysql.err.OperationalError(2003, SECRET), "connection_unavailable"),
        (pymysql.err.OperationalError(2026, SECRET), "tls_failed"),
        (TimeoutError(SECRET), "timeout"),
        (ssl.SSLError(SECRET), "tls_failed"),
        (RuntimeError(SECRET), "unexpected_failure"),
    ],
)
def test_failures_are_redacted_and_resources_closed(monkeypatch, error, category, caplog):
    connection, _, _, resolver = driver(monkeypatch)
    connection.connect.side_effect = error
    report = MySQLConnectionProbe(config(), resolver).check()
    assert report.status == "unhealthy" and report.failure == category
    assert SECRET not in report.model_dump_json() + caplog.text
    connection.close.assert_called_once()


def test_query_failure_closes_cursor_connection_and_wrapped_timeout_is_classified(monkeypatch):
    connection, cursor, _, resolver = driver(monkeypatch)
    error = pymysql.err.OperationalError(2013, SECRET)
    error.__cause__ = TimeoutError(SECRET)
    cursor.execute.side_effect = error
    assert MySQLConnectionProbe(config(), resolver).check().failure == "timeout"
    connection.cursor.return_value.__exit__.assert_called_once()
    connection.close.assert_called_once()


def test_driver_wrapped_certificate_failure_preserves_tls_category(monkeypatch):
    connection, _, _, resolver = driver(monkeypatch)
    wrapped = pymysql.err.OperationalError(2003, SECRET)
    wrapped.__context__ = ssl.SSLCertVerificationError(SECRET)
    connection.connect.side_effect = wrapped
    report = MySQLConnectionProbe(config(), resolver).check()
    assert report.failure == "tls_failed"
    assert SECRET not in report.model_dump_json()


def test_credential_failures_and_source_mismatch_do_not_contact_database(monkeypatch):
    _, _, factory, resolver = driver(monkeypatch)
    resolver.resolve.return_value = credential(uuid4())
    assert MySQLConnectionProbe(config(), resolver).check().failure == "source_mismatch"
    resolver.resolve.side_effect = CredentialUnavailable()
    assert MySQLConnectionProbe(config(), resolver).check().failure == "credential_unavailable"
    factory.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"host": "remote.example"},
        {"host": "localhost"},
        {"port": 0},
        {"connect_timeout_seconds": 31},
        {"read_timeout_seconds": 0},
        {"password": SECRET},
        {"sql": "SELECT 1"},
        {"tls_mode": "verify_identity"},
        {"ca_file": "unexpected.pem"},
    ],
)
def test_configuration_rejects_remote_plaintext_inline_secrets_sql_and_bad_bounds(changes):
    with pytest.raises(ValidationError):
        config(**changes)


def test_tls_downgrade_fails_before_authentication(monkeypatch):
    called = MagicMock()
    monkeypatch.setattr(pymysql.connections.Connection, "_request_authentication", called)
    connection = _TLSGuardConnection(defer_connect=True, ssl=ssl.create_default_context())
    connection.server_capabilities = 0
    with pytest.raises(pymysql.err.OperationalError) as error:
        connection._request_authentication()
    assert error.value.args[0] == 2026
    called.assert_not_called()


def test_tls_handshake_socket_has_a_deadline_before_authentication(monkeypatch):
    called = MagicMock()
    monkeypatch.setattr(pymysql.connections.Connection, "_request_authentication", called)
    connection = _TLSGuardConnection(
        defer_connect=True, ssl=ssl.create_default_context(), connect_timeout=3
    )
    connection.server_capabilities = CLIENT.SSL
    socket = MagicMock()
    connection._sock = socket
    connection._request_authentication()
    socket.settimeout.assert_called_once_with(3)
    called.assert_called_once()


def test_verified_tls_uses_identity_verification_and_bad_ca_fails_closed(monkeypatch):
    _, _, factory, resolver = driver(monkeypatch)
    context = ssl.create_default_context()
    monkeypatch.setattr(ssl, "create_default_context", MagicMock(return_value=context))
    assert (
        MySQLConnectionProbe(config(tls_mode="verify_identity", ca_file="ca.pem"), resolver)
        .check()
        .status
        == "healthy"
    )
    supplied = factory.call_args.kwargs["ssl"]
    assert supplied.check_hostname and supplied.verify_mode == ssl.CERT_REQUIRED
    assert supplied.minimum_version == ssl.TLSVersion.TLSv1_2
    monkeypatch.setattr(
        ssl, "create_default_context", MagicMock(side_effect=FileNotFoundError(SECRET))
    )
    factory.reset_mock()
    assert (
        MySQLConnectionProbe(config(tls_mode="verify_identity", ca_file="missing.pem"), resolver)
        .check()
        .failure
        == "tls_failed"
    )
    factory.assert_not_called()


def test_file_resolver_exact_reference_rotation_bound_and_secret_repr(tmp_path):
    path = tmp_path / "credentials.json"
    resolver = FileCredentialResolver(path)
    with pytest.raises(CredentialUnavailable):
        resolver.resolve("../../private")
    data = {"source_system_id": str(SOURCE), "username": "reader", "password": SECRET}
    path.write_text(json.dumps({"ref": data}))
    resolved = resolver.resolve("ref")
    assert SECRET not in repr(resolved) + resolved.model_dump_json()
    path.write_text(json.dumps({"ref": {**data, "password": "rotated-secret"}}))
    assert resolver.resolve("ref").password.get_secret_value() == "rotated-secret"
    with pytest.raises(CredentialUnavailable):
        resolver.resolve("../../private")
    path.write_bytes(b"x" * 65537)
    with pytest.raises(CredentialUnavailable):
        resolver.resolve("ref")


def test_cli_invalid_configuration_is_redacted_and_credential_failure_has_source_id(
    tmp_path, capsys
):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"password": SECRET}))
    assert main(["--config", str(path), "--credentials", str(tmp_path / "absent")]) == 1
    assert capsys.readouterr().out == '{"error": "invalid_configuration"}\n'
    path.write_text(config().model_dump_json())
    assert main(["--config", str(path), "--credentials", str(tmp_path / "absent")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["source_system_id"] == str(SOURCE)
    assert report["failure"] == "credential_unavailable"
    assert SECRET not in json.dumps(report)


def test_health_cannot_claim_success_with_failure():
    with pytest.raises(ValidationError):
        ConnectionHealth(
            source_system_id=SOURCE,
            status="healthy",
            failure="tls_failed",
            checked_at=datetime.now(UTC),
            elapsed_ms=0,
        )
