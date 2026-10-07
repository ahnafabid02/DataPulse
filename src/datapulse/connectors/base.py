"""Declarative application-mediated access; no arbitrary SQL/model credential surface."""

from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from datapulse.contracts.schema import Contract, DatabaseSchema, Name, TableRef

Fingerprint = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class ColumnProfile(Contract):
    schema_fingerprint: Fingerprint
    table: TableRef
    column: Name
    sampled_at: AwareDatetime
    sampling_method: Name
    scope: Name
    sample_count: int = Field(ge=0, le=1000)
    null_count: int = Field(ge=0)
    distinct_values: tuple[JsonValue, ...] = Field(max_length=1000)
    truncated: bool

    @model_validator(mode="after")
    def bounded_counts(self) -> Self:
        if self.null_count > self.sample_count:
            raise ValueError("Null count cannot exceed sample count")
        if len(self.distinct_values) > self.sample_count:
            raise ValueError("Distinct examples cannot exceed sample count")
        return self


class ExtractionRequest(Contract):
    table: TableRef
    columns: tuple[Name, ...] = Field(min_length=1)
    key_columns: tuple[Name, ...] = Field(min_length=1)
    batch_size: int = Field(default=100, ge=1, le=1000)
    cursor: str | None = None
    updated_since: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_projection(self) -> Self:
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("Projection columns must be distinct")
        if len(set(self.key_columns)) != len(self.key_columns):
            raise ValueError("Extraction keys must be distinct")
        if not set(self.key_columns) <= set(self.columns):
            raise ValueError("Extraction keys must appear in the projection")
        return self


class ExtractedBatch(Contract):
    rows: tuple[dict[str, JsonValue], ...] = Field(max_length=1000)
    next_cursor: str | None
    schema_fingerprint: Fingerprint
    source_snapshot: Name


class DatabaseConnector(Protocol):
    def introspect(self, source_system_id: UUID) -> DatabaseSchema: ...

    def profile_columns(
        self, table: TableRef, columns: tuple[str, ...], limit: int
    ) -> tuple[ColumnProfile, ...]: ...

    def extract_batch(self, request: ExtractionRequest) -> ExtractedBatch: ...

    def close(self) -> None: ...
