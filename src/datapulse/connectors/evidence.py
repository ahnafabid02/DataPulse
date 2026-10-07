"""Bounded clinical evidence through declarative, source-bound read-only requests."""

import hashlib
import json
import math
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID, uuid4

import pymysql
from pydantic import AwareDatetime, Field, JsonValue, model_validator

from datapulse.connectors.base import ColumnProfile, Fingerprint
from datapulse.connectors.connection import ConnectionConfig, CredentialResolver
from datapulse.connectors.introspection import MySQLSchemaScanner, ScanPolicy
from datapulse.connectors.mysql import MySQLConnectionProbe, SourceAccessError
from datapulse.contracts.schema import Contract, DatabaseSchema, Name, TableRef, TableSchema


class EvidencePolicy(Contract):
    max_sample_rows: int = Field(default=20, ge=1, le=20)
    max_check_rows: int = Field(default=10000, ge=1, le=10000)
    max_value_bytes: int = Field(default=256, ge=16, le=4096)
    max_evidence_bytes: int = Field(default=262144, ge=1024, le=1048576)
    deadline_seconds: int = Field(default=60, ge=1, le=300)


class ProfileSelection(Contract):
    table: TableRef
    columns: tuple[Name, ...] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def distinct(self) -> Self:
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("duplicate_columns")
        return self


class RelationshipSelection(Contract):
    source_table: TableRef
    source_columns: tuple[Name, ...] = Field(min_length=1, max_length=8)
    target_table: TableRef
    target_columns: tuple[Name, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def keys(self) -> Self:
        if len(self.source_columns) != len(self.target_columns) or any(
            len(set(columns)) != len(columns)
            for columns in (self.source_columns, self.target_columns)
        ):
            raise ValueError("invalid_key_arity")
        return self


class EvidenceRequest(Contract):
    contract_version: Literal[1] = 1
    source_system_id: UUID
    schema_fingerprint: Fingerprint
    profiles: tuple[ProfileSelection, ...] = Field(default=(), max_length=8)
    relationships: tuple[RelationshipSelection, ...] = Field(default=(), max_length=8)
    policy: EvidencePolicy = EvidencePolicy()

    @model_validator(mode="after")
    def scope(self) -> Self:
        if not self.profiles and not self.relationships:
            raise ValueError("empty_evidence_request")
        if sum(len(p.columns) for p in self.profiles) > 40:
            raise ValueError("column_limit")
        return self


class RelationshipEvidence(Contract):
    relationship: RelationshipSelection
    source_rows_observed: int = Field(ge=0)
    target_rows_observed: int = Field(ge=0)
    complete: bool
    source_null_keys: int | None = Field(default=None, ge=0)
    target_null_keys: int | None = Field(default=None, ge=0)
    target_duplicate_key_groups: int | None = Field(default=None, ge=0)
    source_duplicate_key_groups: int | None = Field(default=None, ge=0)
    unmatched_source_rows: int | None = Field(default=None, ge=0)
    status: Literal["needs_review", "incomplete", "contradicted"]
    equality: Literal["database_native"] = "database_native"
    approved: Literal[False] = False


class EvidenceObservation(Contract):
    contract_version: Literal[1] = 1
    observation_id: UUID
    source_system_id: UUID
    schema_fingerprint: Fingerprint
    observed_at: AwareDatetime
    request: EvidenceRequest
    profiles: tuple[ColumnProfile, ...]
    relationships: tuple[RelationshipEvidence, ...]
    snapshot_method: Literal["innodb_repeatable_read"] = "innodb_repeatable_read"

    def digest(self) -> str:
        body = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode()).hexdigest()


class EvidenceError(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


def _quote(identifier: str) -> str:
    # PyMySQL applies %-style parameter interpolation even to an empty tuple.
    return "`" + identifier.replace("`", "``").replace("%", "%%") + "`"


def _table(table: TableRef) -> str:
    return f"{_quote(table.namespace)}.{_quote(table.name)}"


def _count(rows: tuple[tuple[object, ...], ...]) -> int:
    if len(rows) != 1 or len(rows[0]) != 1 or not isinstance(rows[0][0], int):
        raise EvidenceError("evidence_unavailable")
    return rows[0][0]


def _selection(schema: DatabaseSchema, table: TableRef, columns: tuple[str, ...]) -> TableSchema:
    found = next(
        (t for t in schema.tables if (t.namespace, t.name) == (table.namespace, table.name)), None
    )
    if found is None or not set(columns) <= {c.name for c in found.columns}:
        raise EvidenceError("scope_unavailable")
    return found


def _value(raw: bytes | None, native: str, normalized: str, maximum: int) -> JsonValue:
    if raw is None:
        return None
    if len(raw) > maximum:
        raise EvidenceError("value_limit_exceeded")
    if normalized == "binary":
        return {"encoding": "hex", "value": raw.hex()}
    text = raw.decode("utf-8", errors="strict")
    if normalized == "integer":
        return int(text)
    if normalized == "decimal":
        # Exact DECIMAL is retained as text instead of losing precision in a float.
        if native.lower().startswith(("decimal", "numeric")):
            return str(Decimal(text))
        value = float(text)
        if not math.isfinite(value):
            raise EvidenceError("unsupported_value")
        return value
    return text


class MySQLEvidenceReader:
    def __init__(self, config: ConnectionConfig, credentials: CredentialResolver) -> None:
        self._config = config
        self._probe = MySQLConnectionProbe(config, credentials)
        self._scanner = MySQLSchemaScanner(config, credentials, ScanPolicy())

    def capture(self, request: EvidenceRequest, schema: DatabaseSchema) -> EvidenceObservation:
        if request.source_system_id != self._config.source_system_id or (
            schema.source_system_id != request.source_system_id
            or schema.database_name != self._config.database
        ):
            raise EvidenceError("source_mismatch")
        if schema.structural_fingerprint() != request.schema_fingerprint:
            raise EvidenceError("schema_changed")
        tables: dict[tuple[str, str], TableRef] = {}
        for item in request.profiles:
            _selection(schema, item.table, item.columns)
            tables[(item.table.namespace, item.table.name)] = item.table
        for join in request.relationships:
            left = _selection(schema, join.source_table, join.source_columns)
            right = _selection(schema, join.target_table, join.target_columns)
            types = {c.name: c.normalized_type for c in left.columns}
            target_types = {c.name: c.normalized_type for c in right.columns}
            if any(
                types[a] != target_types[b] or types[a] not in {"integer", "string", "uuid"}
                for a, b in zip(join.source_columns, join.target_columns, strict=True)
            ):
                raise EvidenceError("unsupported_relationship_type")
            for table in (join.source_table, join.target_table):
                tables[(table.namespace, table.name)] = table
        if any(table.namespace != self._config.database for table in tables.values()):
            raise EvidenceError("scope_unavailable")
        started = time.monotonic()
        policy = request.policy

        def remaining() -> float:
            seconds = policy.deadline_seconds - (time.monotonic() - started)
            if seconds <= 0:
                raise EvidenceError("timeout")
            return seconds

        try:
            fresh = self._scanner.introspect(request.source_system_id)
            remaining()
            if fresh.structural_fingerprint() != request.schema_fingerprint:
                raise EvidenceError("schema_changed")
            with self._probe.open_readonly() as connection:

                def query(
                    sql: str, args: tuple[object, ...] = ()
                ) -> tuple[tuple[object, ...], ...]:
                    seconds = remaining()
                    with connection.cursor() as cursor:
                        if self._config.vendor == "mariadb":
                            cursor.execute("SET SESSION max_statement_time=%s", (seconds,))
                        else:
                            cursor.execute(
                                "SET SESSION max_execution_time=%s", (int(seconds * 1000),)
                            )
                        cursor.execute(sql, args)
                        result = tuple(tuple(row) for row in cursor.fetchall())
                    remaining()
                    return result

                query("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                query("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
                for table in tables.values():
                    engine = query(
                        "SELECT ENGINE FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND TABLE_TYPE='BASE TABLE'",
                        (table.namespace, table.name),
                    )
                    if engine != (("InnoDB",),):
                        raise EvidenceError("unsupported_snapshot_engine")
                profiles: list[ColumnProfile] = []
                byte_count = 0
                observed_at = datetime.now(UTC)
                for selection in request.profiles:
                    table_schema = _selection(schema, selection.table, selection.columns)
                    projected = ",".join(
                        f"LEFT(CAST({_quote(c)} AS BINARY),%s)" for c in selection.columns
                    )
                    order = (
                        " ORDER BY " + ",".join(_quote(c) for c in table_schema.primary_key)
                        if table_schema.primary_key
                        else ""
                    )
                    rows = query(
                        f"SELECT {projected} FROM {_table(selection.table)}{order} LIMIT %s",
                        (
                            *([policy.max_value_bytes + 1] * len(selection.columns)),
                            policy.max_sample_rows + 1,
                        ),
                    )
                    truncated = len(rows) > policy.max_sample_rows
                    rows = rows[: policy.max_sample_rows]
                    for index, column in enumerate(selection.columns):
                        info = next(c for c in table_schema.columns if c.name == column)
                        values: list[JsonValue] = []
                        null_count = 0
                        for row in rows:
                            raw = row[index]
                            if raw is not None and not isinstance(raw, bytes):
                                raise EvidenceError("unsupported_value")
                            value = _value(
                                raw, info.native_type, info.normalized_type, policy.max_value_bytes
                            )
                            null_count += value is None
                            byte_count += len(json.dumps(value).encode())
                            if byte_count > policy.max_evidence_bytes:
                                raise EvidenceError("limit_exceeded")
                            if value is not None and value not in values:
                                values.append(value)
                        profiles.append(
                            ColumnProfile(
                                schema_fingerprint=request.schema_fingerprint,
                                table=selection.table,
                                column=column,
                                sampled_at=observed_at,
                                sampling_method="primary_key_prefix"
                                if table_schema.primary_key
                                else "unordered_prefix",
                                scope="bounded_table_prefix",
                                sample_count=len(rows),
                                null_count=null_count,
                                distinct_values=tuple(values),
                                truncated=truncated,
                            )
                        )
                joins: list[RelationshipEvidence] = []
                for join in request.relationships:
                    counts = [
                        len(
                            query(
                                f"SELECT 1 FROM {_table(t)} LIMIT %s", (policy.max_check_rows + 1,)
                            )
                        )
                        for t in (join.source_table, join.target_table)
                    ]
                    if any(count > policy.max_check_rows for count in counts):
                        joins.append(
                            RelationshipEvidence(
                                relationship=join,
                                source_rows_observed=counts[0],
                                target_rows_observed=counts[1],
                                complete=False,
                                status="incomplete",
                            )
                        )
                        continue
                    metrics: list[tuple[int, int]] = []
                    for table, columns in (
                        (join.source_table, join.source_columns),
                        (join.target_table, join.target_columns),
                    ):
                        nulls = " OR ".join(f"{_quote(c)} IS NULL" for c in columns)
                        nonnull = " AND ".join(f"{_quote(c)} IS NOT NULL" for c in columns)
                        null_count = _count(
                            query(f"SELECT COUNT(*) FROM {_table(table)} WHERE {nulls}")
                        )
                        keys = ",".join(_quote(c) for c in columns)
                        duplicates = _count(
                            query(
                                f"SELECT COUNT(*) FROM (SELECT {keys} FROM {_table(table)} "
                                f"WHERE {nonnull} GROUP BY {keys} HAVING COUNT(*)>1) AS d"
                            )
                        )
                        metrics.append((null_count, duplicates))
                    on = " AND ".join(
                        f"s.{_quote(a)}=t.{_quote(b)}"
                        for a, b in zip(join.source_columns, join.target_columns, strict=True)
                    )
                    nonnull = " AND ".join(
                        f"s.{_quote(c)} IS NOT NULL" for c in join.source_columns
                    )
                    unmatched = _count(
                        query(
                            f"SELECT COUNT(*) FROM {_table(join.source_table)} s "
                            f"WHERE {nonnull} AND NOT EXISTS (SELECT 1 FROM "
                            f"{_table(join.target_table)} t WHERE {on})"
                        )
                    )
                    joins.append(
                        RelationshipEvidence(
                            relationship=join,
                            source_rows_observed=counts[0],
                            target_rows_observed=counts[1],
                            complete=True,
                            source_null_keys=metrics[0][0],
                            target_null_keys=metrics[1][0],
                            source_duplicate_key_groups=metrics[0][1],
                            target_duplicate_key_groups=metrics[1][1],
                            unmatched_source_rows=unmatched,
                            status="contradicted"
                            if metrics[1][1] or unmatched or not counts[1]
                            else "needs_review",
                        )
                    )
                connection.rollback()
            remaining()
            after = self._scanner.introspect(request.source_system_id)
            remaining()
            if after.structural_fingerprint() != request.schema_fingerprint:
                raise EvidenceError("schema_changed")
            result = EvidenceObservation(
                observation_id=uuid4(),
                source_system_id=request.source_system_id,
                schema_fingerprint=request.schema_fingerprint,
                observed_at=observed_at,
                request=request,
                profiles=tuple(profiles),
                relationships=tuple(joins),
            )
            if len(result.model_dump_json().encode()) > policy.max_evidence_bytes:
                raise EvidenceError("limit_exceeded")
            return result
        except SourceAccessError as error:
            raise EvidenceError(error.category) from None
        except EvidenceError:
            raise
        except Exception as error:
            if (
                isinstance(error, pymysql.err.Error)
                and error.args
                and error.args[0] in (1969, 3024)
            ):
                raise EvidenceError("timeout") from None
            raise EvidenceError("evidence_unavailable") from None
