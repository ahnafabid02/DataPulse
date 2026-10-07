"""Vendor connection probe. No EHR branching, schema scans or caller-supplied SQL."""

import ssl
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from socket import socket

import pymysql
from pymysql.constants import CLIENT

from datapulse.connectors.connection import (
    ConnectionConfig,
    ConnectionHealth,
    CredentialResolver,
    CredentialUnavailable,
    Failure,
)


class _TLSGuardConnection(pymysql.connections.Connection):
    server_capabilities: int
    _sock: socket | None

    def _request_authentication(self) -> None:
        # PyMySQL 1.1.2 otherwise falls back to plaintext when CLIENT.SSL is absent.
        # Reject before its authentication packet can contain any credential material.
        if self.ssl and not self.server_capabilities & CLIENT.SSL:
            raise pymysql.err.OperationalError(2026, "TLS required")
        if self.ssl and self._sock is not None:
            # The driver clears the TCP connect timeout before wrapping this socket.
            # Bound TLS negotiation too; cursor reads use the separate read timeout.
            self._sock.settimeout(self.connect_timeout)
        super()._request_authentication()  # type: ignore[misc]


def _restricted_grants(grants: tuple[tuple[object, ...], ...], database: str) -> bool:
    has_select = False
    for row in grants:
        if not row or not isinstance(row[0], str):
            return False
        grant = row[0]
        if "WITH GRANT OPTION" in grant:
            return False
        if grant.startswith("GRANT USAGE ON *.* TO "):
            continue
        if grant.startswith(f"GRANT SELECT ON `{database}`.* TO "):
            has_select = True
        else:
            return False
    return has_select


def _driver_failure(error: pymysql.err.Error) -> Failure:
    code = error.args[0] if error.args else None
    if code == 1045:
        return "authentication_failed"
    if code in (1044, 1142, 1143):
        return "database_denied"
    if code == 1049:
        return "database_unavailable"
    if code == 2026:
        return "tls_failed"
    if code in (1969, 3024):
        return "timeout"
    if code in (2002, 2003, 2006, 2013):
        # The driver wraps socket timeouts; inspect cause without exposing its text.
        current: BaseException | None = error
        for _ in range(8):
            if current is None:
                break
            if isinstance(current, ssl.SSLError):
                return "tls_failed"
            if isinstance(current, TimeoutError):
                return "timeout"
            original = getattr(current, "original_exception", None)
            current = (
                current.__cause__
                or current.__context__
                or (original if isinstance(original, BaseException) else None)
            )
        return "connection_unavailable"
    return "unexpected_failure"


class SourceAccessError(Exception):
    def __init__(self, category: Failure) -> None:
        self.category = category
        super().__init__(category)


class MySQLConnectionProbe:
    def __init__(self, config: ConnectionConfig, credentials: CredentialResolver) -> None:
        self._config = config
        self._credentials = credentials

    @contextmanager
    def open_readonly(self) -> Iterator[_TLSGuardConnection]:
        """Authenticate, verify scope/grants, and always close the hospital socket."""
        connection = None
        try:
            config = self._config
            credential = self._credentials.resolve(config.credential_ref)
            if credential.source_system_id != config.source_system_id:
                raise SourceAccessError("source_mismatch")
            context = None
            if config.tls_mode == "verify_identity":
                try:
                    context = ssl.create_default_context(cafile=str(config.ca_file))
                    context.minimum_version = ssl.TLSVersion.TLSv1_2
                except (OSError, ssl.SSLError):
                    raise SourceAccessError("tls_failed") from None
            connection = _TLSGuardConnection(
                host=config.host,
                port=config.port,
                database=config.database,
                user=credential.username.get_secret_value(),
                password=credential.password.get_secret_value(),
                charset="utf8mb4",
                connect_timeout=config.connect_timeout_seconds,
                read_timeout=config.read_timeout_seconds,
                write_timeout=config.read_timeout_seconds,
                ssl=context,
                ssl_disabled=config.tls_mode == "disabled_local_demo",
                local_infile=False,
                autocommit=True,
                defer_connect=True,
            )
            connection.connect()
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION TRANSACTION READ ONLY")
                cursor.execute("SELECT DATABASE(), VERSION(), 1")
                row = cursor.fetchone()
                if (
                    not row
                    or len(row) != 3
                    or row[0] != config.database
                    or not isinstance(row[1], str)
                    or row[2] != 1
                ):
                    raise SourceAccessError("database_unavailable")
                if ("MariaDB" in row[1]) != (config.vendor == "mariadb"):
                    raise SourceAccessError("vendor_mismatch")
                cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
                if not _restricted_grants(cursor.fetchall(), config.database):
                    raise SourceAccessError("unsafe_privileges")
            yield connection
        except CredentialUnavailable:
            raise SourceAccessError("credential_unavailable") from None
        except ssl.SSLError:
            raise SourceAccessError("tls_failed") from None
        except TimeoutError:
            raise SourceAccessError("timeout") from None
        except pymysql.err.Error as error:
            raise SourceAccessError(_driver_failure(error)) from None
        except OSError:
            raise SourceAccessError("connection_unavailable") from None
        finally:
            if connection is not None and connection.open:
                with suppress(OSError, pymysql.err.Error):
                    connection.close()

    def check(self) -> ConnectionHealth:
        started = time.monotonic()
        checked_at = datetime.now(UTC)
        failure: Failure | None = None
        try:
            with self.open_readonly():
                pass
        except SourceAccessError as error:
            failure = error.category
        except Exception:
            failure = "unexpected_failure"
        return ConnectionHealth(
            source_system_id=self._config.source_system_id,
            status="healthy" if failure is None else "unhealthy",
            checked_at=checked_at,
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
            failure=failure,
        )
