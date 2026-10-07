"""Immutable normalized database schema; samples are outside the structural scan."""

import hashlib
import json
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Name = Annotated[str, Field(min_length=1, pattern=r"\S")]
Vendor = Literal["postgresql", "mysql", "mariadb", "sqlserver", "oracle"]
NormalizedType = Literal[
    "string",
    "integer",
    "decimal",
    "boolean",
    "date",
    "datetime",
    "binary",
    "json",
    "uuid",
    "unknown",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TableRef(Contract):
    namespace: str
    name: Name


class ColumnSchema(Contract):
    name: Name
    ordinal: int = Field(ge=0)
    native_type: Name
    normalized_type: NormalizedType
    nullable: bool
    default: str | None = None
    comment: str | None = None
    precision: int | None = Field(default=None, ge=0)
    scale: int | None = Field(default=None, ge=0)
    length: int | None = Field(default=None, ge=0)


class ForeignKeySchema(Contract):
    name: Name
    columns: tuple[Name, ...] = Field(min_length=1)
    referenced_table: TableRef
    referenced_columns: tuple[Name, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def matching_arity(self) -> Self:
        if len(self.columns) != len(self.referenced_columns):
            raise ValueError("Foreign key column lists must have equal arity")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("Foreign key columns must be distinct")
        if len(set(self.referenced_columns)) != len(self.referenced_columns):
            raise ValueError("Referenced key columns must be distinct")
        return self


class UniqueConstraintSchema(Contract):
    name: Name
    columns: tuple[Name, ...] = Field(min_length=1)


class IndexSchema(Contract):
    name: Name
    columns: tuple[Name, ...] = ()
    unique: bool = False
    expression: str | None = None

    @model_validator(mode="after")
    def has_index_definition(self) -> Self:
        if not self.columns and not (self.expression and self.expression.strip()):
            raise ValueError("Index must specify columns or an expression")
        return self


class RelationshipHint(Contract):
    columns: tuple[Name, ...] = Field(min_length=1)
    referenced_table: TableRef
    referenced_columns: tuple[Name, ...] = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: tuple[Name, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def matching_arity(self) -> Self:
        if len(self.columns) != len(self.referenced_columns):
            raise ValueError("Inferred relationship column lists must have equal arity")
        return self


class TableSchema(Contract):
    namespace: str
    name: Name
    comment: str | None = None
    columns: tuple[ColumnSchema, ...] = Field(min_length=1)
    primary_key: tuple[Name, ...] = ()
    foreign_keys: tuple[ForeignKeySchema, ...] = ()
    unique_constraints: tuple[UniqueConstraintSchema, ...] = ()
    indexes: tuple[IndexSchema, ...] = ()
    relationship_hints: tuple[RelationshipHint, ...] = ()

    @model_validator(mode="after")
    def valid_local_references(self) -> Self:
        names = {column.name for column in self.columns}
        if len(names) != len(self.columns):
            raise ValueError("Duplicate column names")
        if len({column.ordinal for column in self.columns}) != len(self.columns):
            raise ValueError("Duplicate column ordinals")
        groups = [self.primary_key]
        for collection in (self.foreign_keys, self.unique_constraints, self.indexes):
            if len({item.name for item in collection}) != len(collection):
                raise ValueError("Duplicate constraint/index names")
            groups.extend(item.columns for item in collection)
        groups.extend(item.columns for item in self.relationship_hints)
        for columns in groups:
            if not set(columns) <= names:
                raise ValueError("Constraint references an unknown local column")
            if len(set(columns)) != len(columns):
                raise ValueError("Constraint column lists must be distinct")
        return self


class DatabaseSchema(Contract):
    contract_version: Literal[1] = 1
    source_system_id: UUID
    database_name: Name
    vendor: Vendor
    scanned_at: AwareDatetime
    tables: tuple[TableSchema, ...]

    @model_validator(mode="after")
    def valid_relationships(self) -> Self:
        tables = {(table.namespace, table.name): table for table in self.tables}
        if len(tables) != len(self.tables):
            raise ValueError("Duplicate qualified table names")
        for table in self.tables:
            for fk in table.foreign_keys:
                target = tables.get((fk.referenced_table.namespace, fk.referenced_table.name))
                if target is not None:
                    target_columns = {column.name for column in target.columns}
                    if not set(fk.referenced_columns) <= target_columns:
                        raise ValueError("Foreign key references an unknown scanned target column")
        return self

    def structural_fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"scanned_at"})
        tables = payload["tables"]
        tables.sort(key=lambda table: (table["namespace"], table["name"]))
        for table in tables:
            table.pop("comment")
            table.pop("relationship_hints")
            table["columns"].sort(key=lambda column: column["ordinal"])
            for column in table["columns"]:
                column.pop("comment")
                column.pop("default")
            for key in ("foreign_keys", "unique_constraints", "indexes"):
                table[key].sort(key=lambda item: item["name"])
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
