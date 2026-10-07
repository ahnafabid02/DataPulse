"""Bounded source metadata access. No record sampling or caller-supplied SQL."""

import json
import time
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

import pymysql
from pydantic import Field

from datapulse.connectors.connection import ConnectionConfig, CredentialResolver
from datapulse.connectors.mysql import MySQLConnectionProbe, SourceAccessError
from datapulse.contracts.schema import Contract, DatabaseSchema, NormalizedType, TableSchema


class ScanPolicy(Contract):
    tables: tuple[str, ...] = Field(default=(), max_length=2000)
    max_tables: int = Field(default=1000, ge=1, le=2000)
    max_columns: int = Field(default=30000, ge=1, le=100000)
    max_metadata_bytes: int = Field(default=16000000, ge=1024, le=32000000)
    deadline_seconds: int = Field(default=60, ge=1, le=300)


ScanFailure = Literal["limit_exceeded", "scope_unavailable", "schema_changed", "invalid_metadata"]


class ScanError(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


class SchemaScanner(Protocol):
    def introspect(self, source_system_id: UUID) -> DatabaseSchema: ...


def normalized_type(native: str) -> NormalizedType:
    base = native.lower().split("(", 1)[0].split()[0]
    if base in {"tinyint", "smallint", "mediumint", "int", "integer", "bigint"}:
        return "integer"
    if base in {"decimal", "numeric", "float", "double", "real"}:
        return "decimal"
    if base in {"char", "varchar", "text", "tinytext", "mediumtext", "longtext", "enum", "set"}:
        return "string"
    if base in {"binary", "varbinary", "blob", "tinyblob", "mediumblob", "longblob", "bit"}:
        return "binary"
    if base in {"datetime", "timestamp", "time"}:
        return "datetime"
    if base == "date":
        return "date"
    if base == "json":
        return "json"
    if base == "uuid":
        return "uuid"
    return "unknown"


class MySQLSchemaScanner:
    def __init__(
        self, config: ConnectionConfig, credentials: CredentialResolver, policy: ScanPolicy
    ) -> None:
        self._config = config
        self._probe = MySQLConnectionProbe(config, credentials)
        self._policy = policy

    def introspect(self, source_system_id: UUID) -> DatabaseSchema:
        if source_system_id != self._config.source_system_id:
            raise ScanError("source_mismatch")
        started = time.monotonic()
        try:
            with self._probe.open_readonly() as connection:
                first = self._read(connection, started)
                # INFORMATION_SCHEMA is not a transactional schema snapshot. Refuse a
                # changing metadata observation rather than claiming atomic DDL isolation.
                second = self._read(connection, started)
                if first.model_dump(exclude={"scanned_at"}) != second.model_dump(
                    exclude={"scanned_at"}
                ):
                    raise ScanError("schema_changed")
                return second
        except SourceAccessError as error:
            raise ScanError(error.category) from None
        except ScanError:
            raise
        except (ValueError, TypeError, KeyError, IndexError):
            raise ScanError("invalid_metadata") from None
        except Exception:
            raise ScanError("unexpected_failure") from None

    def _read(self, connection: pymysql.connections.Connection, started: float) -> DatabaseSchema:
        policy = self._policy
        database = self._config.database
        byte_count = 0

        def query(sql: str, maximum: int) -> list[tuple[object, ...]]:
            nonlocal byte_count
            rows: list[tuple[object, ...]] = []
            if time.monotonic() - started >= policy.deadline_seconds:
                raise ScanError("timeout")
            cursor = connection.cursor(pymysql.cursors.SSCursor)
            try:
                cursor.execute(sql + " LIMIT %s", (database, maximum + 1))
                for row in cursor:
                    if time.monotonic() - started >= policy.deadline_seconds:
                        connection.close()
                        raise ScanError("timeout")
                    byte_count += len(json.dumps(row, default=str).encode())
                    if len(rows) >= maximum or byte_count > policy.max_metadata_bytes:
                        # Closing a streaming cursor drains its result. Close the socket
                        # first so rejected oversized metadata is not drained unboundedly.
                        connection.close()
                        raise ScanError("limit_exceeded")
                    rows.append(tuple(row))
            finally:
                if connection.open:
                    cursor.close()
                else:
                    # The pinned driver's streaming close otherwise drains a dead
                    # socket and can mask the original bounded-scan failure.
                    cursor.connection = None  # type: ignore[assignment]
                    result = getattr(cursor, "_result", None)
                    if result is not None:
                        # MySQLResult.__del__ also drains unless this pinned-driver
                        # flag is cleared after intentionally aborting its socket.
                        result.unbuffered_active = False
            return rows

        tables = query(
            "SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE' ORDER BY BINARY TABLE_NAME",
            policy.max_tables,
        )
        available = {str(row[0]) for row in tables}
        if policy.tables and not set(policy.tables) <= available:
            raise ScanError("scope_unavailable")
        selected = set(policy.tables) if policy.tables else available
        columns = query(
            "SELECT TABLE_NAME,COLUMN_NAME,ORDINAL_POSITION,COLUMN_TYPE,IS_NULLABLE,"
            "COLUMN_DEFAULT,COLUMN_COMMENT,NUMERIC_PRECISION,NUMERIC_SCALE,"
            "CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s ORDER BY BINARY TABLE_NAME,ORDINAL_POSITION",
            policy.max_columns,
        )
        keys = query(
            # MariaDB hides TABLE_CONSTRAINTS from SELECT-only accounts. KCU is
            # visible with SELECT and identifies declared FK/PK/unique membership.
            "SELECT TABLE_NAME,CONSTRAINT_NAME,CASE WHEN REFERENCED_TABLE_NAME IS NOT NULL "
            "THEN 'FOREIGN KEY' WHEN CONSTRAINT_NAME='PRIMARY' THEN 'PRIMARY KEY' "
            "ELSE 'UNIQUE' END,COLUMN_NAME,ORDINAL_POSITION,REFERENCED_TABLE_SCHEMA,"
            "REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME "
            "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s "
            "ORDER BY BINARY TABLE_NAME,BINARY CONSTRAINT_NAME,ORDINAL_POSITION",
            policy.max_columns * 8,
        )
        indexes = query(
            "SELECT TABLE_NAME,INDEX_NAME,COLUMN_NAME,NON_UNIQUE,SEQ_IN_INDEX "
            "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=%s "
            "ORDER BY BINARY TABLE_NAME,BINARY INDEX_NAME,SEQ_IN_INDEX",
            policy.max_columns * 8,
        )
        result = []
        for name, comment in tables:
            if name not in selected:
                continue
            fields = [
                dict(
                    name=c[1],
                    ordinal=int(str(c[2])) - 1,
                    native_type=c[3],
                    normalized_type=normalized_type(str(c[3])),
                    nullable=c[4] == "YES",
                    default=None if c[5] is None else str(c[5]),
                    comment=c[6] or None,
                    precision=c[7],
                    scale=c[8],
                    length=c[9],
                )
                for c in columns
                if c[0] == name
            ]
            key_groups: dict[str, list[tuple[object, ...]]] = {}
            for key in keys:
                if key[0] == name:
                    key_groups.setdefault(str(key[1]), []).append(key)
            primary: tuple[str, ...] = ()
            foreign, unique = [], []
            for key_name, group in key_groups.items():
                ordered = tuple(str(row[3]) for row in group)
                if group[0][2] == "PRIMARY KEY":
                    primary = ordered
                elif group[0][2] == "UNIQUE":
                    unique.append(dict(name=key_name, columns=ordered))
                elif group[0][2] == "FOREIGN KEY":
                    foreign.append(
                        dict(
                            name=key_name,
                            columns=ordered,
                            referenced_table=dict(namespace=group[0][5], name=group[0][6]),
                            referenced_columns=tuple(str(row[7]) for row in group),
                        )
                    )
            index_groups: dict[str, list[tuple[object, ...]]] = {}
            for index in indexes:
                if index[0] == name:
                    index_groups.setdefault(str(index[1]), []).append(index)
            index_defs = []
            for index_name, group in index_groups.items():
                if any(row[2] is None for row in group):
                    raise ScanError("invalid_metadata")
                index_defs.append(
                    dict(
                        name=index_name,
                        columns=tuple(str(r[2]) for r in group),
                        unique=group[0][3] == 0,
                    )
                )
            result.append(
                TableSchema.model_validate(
                    dict(
                        namespace=database,
                        name=name,
                        comment=comment or None,
                        columns=fields,
                        primary_key=primary,
                        foreign_keys=foreign,
                        unique_constraints=unique,
                        indexes=index_defs,
                    )
                )
            )
        return DatabaseSchema(
            source_system_id=self._config.source_system_id,
            database_name=database,
            vendor=self._config.vendor,
            scanned_at=datetime.now(UTC),
            tables=tuple(result),
        )
