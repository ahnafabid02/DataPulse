"""Complete source-field inventory; classifications never silently exclude fields."""

from typing import Literal
from uuid import UUID

from datapulse.connectors.base import Fingerprint
from datapulse.contracts.schema import Contract, DatabaseSchema, Name, TableRef


class PendingField(Contract):
    table: TableRef
    column: Name
    status: Literal["unresolved"] = "unresolved"
    reason: Literal["awaiting_human_coverage_review"] = "awaiting_human_coverage_review"


class CoverageInventory(Contract):
    contract_version: Literal[1] = 1
    source_system_id: UUID
    schema_fingerprint: Fingerprint
    fields: tuple[PendingField, ...]
    complete_clinical_mapping: Literal[False] = False


def inventory(schema: DatabaseSchema) -> CoverageInventory:
    return CoverageInventory(
        source_system_id=schema.source_system_id,
        schema_fingerprint=schema.structural_fingerprint(),
        fields=tuple(
            PendingField(
                table=TableRef(namespace=table.namespace, name=table.name), column=column.name
            )
            for table in sorted(schema.tables, key=lambda t: (t.namespace, t.name))
            for column in sorted(table.columns, key=lambda c: (c.ordinal, c.name))
        ),
    )
