"""Bounded M4 envelopes and non-executable, allowlisted transformation proposals."""

from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from datapulse.connectors.base import ColumnProfile, Fingerprint
from datapulse.contracts.schema import Contract, TableRef, TableSchema
from datapulse.mapping.catalog import TargetCandidate


class FieldRef(Contract):
    table: TableRef
    column: str = Field(min_length=1, max_length=256)


class Copy(Contract):
    op: Literal["copy"] = "copy"
    source: FieldRef


class LiteralValue(Contract):
    op: Literal["literal"] = "literal"
    value: JsonValue


class Trim(Contract):
    op: Literal["trim"] = "trim"
    source: FieldRef


class DateParse(Contract):
    op: Literal["date_parse"] = "date_parse"
    source: FieldRef
    format: str = Field(min_length=1, max_length=64)
    timezone: str = Field(min_length=1, max_length=64)


class CodeMap(Contract):
    op: Literal["code_map"] = "code_map"
    source: FieldRef
    values: dict[str, str] = Field(min_length=1, max_length=64)
    on_unmapped: Literal["quarantine", "missing"]


class Concatenate(Contract):
    op: Literal["concatenate"] = "concatenate"
    sources: tuple[FieldRef, ...] = Field(min_length=1, max_length=8)
    separator: str = Field(max_length=16)


class Reference(Contract):
    op: Literal["reference"] = "reference"
    source: FieldRef
    target_resource: str = Field(min_length=1, max_length=64)
    on_missing: Literal["quarantine", "missing"]


class ArrayGroup(Contract):
    op: Literal["array_group"] = "array_group"
    source: FieldRef
    group_id: str = Field(min_length=1, max_length=64)


class Conditional(Contract):
    op: Literal["conditional"] = "conditional"
    source: FieldRef
    equals: JsonValue
    then: "TransformNode"
    otherwise: "TransformNode"


TransformNode = Annotated[
    Copy
    | LiteralValue
    | Trim
    | DateParse
    | CodeMap
    | Concatenate
    | Reference
    | ArrayGroup
    | Conditional,
    Field(discriminator="op"),
]
Conditional.model_rebuild()
OPERATIONS = (
    "copy",
    "literal",
    "trim",
    "date_parse",
    "code_map",
    "concatenate",
    "conditional",
    "reference",
    "array_group",
)


class Confidence(Contract):
    score: float | None = Field(default=None, ge=0, le=1)
    method: str = Field(min_length=1, max_length=64)
    calibration_version: str | None = Field(default=None, max_length=64)
    reasons: tuple[str, ...] = Field(min_length=1, max_length=8)


class RecordSample(Contract):
    evidence_id: UUID
    table: TableRef
    values: dict[str, JsonValue] = Field(max_length=40)


class FieldProposal(Contract):
    source_refs: tuple[FieldRef, ...] = Field(max_length=8)
    candidate_id: str = Field(min_length=1, max_length=128)
    target_path: str = Field(min_length=1, max_length=256)
    group_id: str | None = Field(default=None, max_length=64)
    mapping_type: Literal["direct", "transformed", "constant", "reference"]
    transformation: TransformNode
    confidence: Confidence
    evidence_refs: tuple[UUID, ...] = Field(min_length=1, max_length=16)
    rationale: str = Field(min_length=1, max_length=1000)


class UnresolvedField(Contract):
    source_refs: tuple[FieldRef, ...] = Field(min_length=1, max_length=8)
    reason: str = Field(min_length=1, max_length=1000)


class MappingTaskOutput(Contract):
    task_id: UUID
    proposals: tuple[FieldProposal, ...] = Field(max_length=40)
    unresolved: tuple[UnresolvedField, ...] = Field(max_length=40)


def task_output_schema(
    task_id: UUID,
    tables: tuple[TableSchema, ...],
    candidates: tuple[TargetCandidate, ...],
    operations: tuple[str, ...] = OPERATIONS,
) -> dict[str, Any]:
    schema = MappingTaskOutput.model_json_schema()
    schema["properties"]["task_id"]["const"] = str(task_id)
    definitions = schema["$defs"]
    field = definitions["FieldProposal"]["properties"]
    field["candidate_id"]["enum"] = [c.id for c in candidates]
    field["target_path"]["enum"] = [c.element_path for c in candidates]
    field["evidence_refs"]["items"]["enum"] = [str(task_id)]
    if candidates and all("[]" in c.element_path for c in candidates):
        field["group_id"] = {"type": "string", "minLength": 1, "maxLength": 64}
    elif candidates and all("[]" not in c.element_path for c in candidates):
        field["group_id"] = {"type": "null"}
    if "conditional" not in operations:
        transform = field["transformation"]
        transform["oneOf"] = [
            item
            for item in transform["oneOf"]
            if item["$ref"].rsplit("/", 1)[-1]
            in {
                {
                    "copy": "Copy",
                    "trim": "Trim",
                    "date_parse": "DateParse",
                    "code_map": "CodeMap",
                    "literal": "LiteralValue",
                    "concatenate": "Concatenate",
                    "reference": "Reference",
                    "array_group": "ArrayGroup",
                }[op]
                for op in operations
            }
        ]
        transform.pop("discriminator", None)
        if len(transform["oneOf"]) == 1:
            field["transformation"] = transform["oneOf"][0]
        mapping_types = {"copy": "direct", "literal": "constant", "reference": "reference"}
        field["mapping_type"]["enum"] = sorted(
            {mapping_types.get(op, "transformed") for op in operations}
        )
    definitions["Confidence"]["properties"]["calibration_version"] = {"type": "null"}
    definitions["FieldProposal"]["required"] = list(field)
    definitions["FieldRef"]["properties"]["column"]["enum"] = [
        c.name for table in tables for c in table.columns
    ]
    definitions["TableRef"]["properties"]["namespace"]["enum"] = list({t.namespace for t in tables})
    definitions["TableRef"]["properties"]["name"]["enum"] = list({t.name for t in tables})
    # Drop unreachable AST alternatives; sending their grammars wastes local context
    # and invites operation choices that this task cannot support.
    needed = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                name = value["$ref"].rsplit("/", 1)[-1]
                if name not in needed:
                    needed.add(name)
                    visit(definitions[name])
            for key, child in value.items():
                if key != "$defs":
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    schema["$defs"] = {
        name: definition for name, definition in definitions.items() if name in needed
    }
    return schema


class MappingTask(Contract):
    contract_version: Literal[1] = 1
    task_id: UUID
    source_system_id: UUID
    database_name: str
    schema_fingerprint: Fingerprint
    tables: tuple[TableSchema, ...] = Field(min_length=1, max_length=8)
    profiles: tuple[ColumnProfile, ...] = Field(default=(), max_length=40)
    record_samples: tuple[RecordSample, ...] = Field(default=(), max_length=20)
    candidates: tuple[TargetCandidate, ...] = Field(max_length=12)
    allowed_operations: tuple[str, ...] = OPERATIONS
    output_schema: dict[str, Any]
    max_output_tokens: int = Field(default=2048, ge=256, le=4096)

    @model_validator(mode="after")
    def bounds_and_identity(self) -> Self:
        if sum(len(t.columns) for t in self.tables) > 40:
            raise ValueError("Column task limit")
        if len({(t.namespace, t.name) for t in self.tables}) != len(self.tables):
            raise ValueError("Duplicate task tables")
        if len({c.id for c in self.candidates}) != len(self.candidates):
            raise ValueError("Duplicate candidates")
        if not set(self.allowed_operations) <= set(OPERATIONS):
            raise ValueError("Unsupported operations")
        expected = task_output_schema(
            self.task_id, self.tables, self.candidates, self.allowed_operations
        )
        if self.output_schema != expected:
            raise ValueError("Output schema must be host-owned")
        return self


class MappingLimits(Contract):
    max_tables_per_task: int = Field(default=8, ge=1, le=8)
    max_columns_per_task: int = Field(default=40, ge=1, le=40)
    max_sample_rows: int = Field(default=20, ge=0, le=20)
    max_candidates: int = Field(default=6, ge=1, le=12)
    max_tokens: int = Field(default=2048, ge=256, le=4096)


class PackageRef(Contract):
    id: Literal["hl7.fhir.r4.core"] = "hl7.fhir.r4.core"
    version: Literal["4.0.1"] = "4.0.1"


class MappingTarget(Contract):
    fhir_version: Literal["4.0.1"] = "4.0.1"
    packages: tuple[PackageRef, ...] = (PackageRef(),)

    @model_validator(mode="after")
    def exact_core(self) -> Self:
        if self.packages != (PackageRef(),):
            raise ValueError("Core catalog required")
        return self


class MappingScope(Contract):
    tables: tuple[TableRef, ...] = Field(min_length=1, max_length=1000)
    domains: tuple[str, ...] = Field(default=(), max_length=8)


class MappingRunInput(Contract):
    contract_version: Literal[1] = 1
    run_id: UUID
    source_system_id: UUID
    database_name: str
    schema_fingerprint: Fingerprint
    schema_scan_id: UUID
    scope: MappingScope
    target: MappingTarget = MappingTarget()
    limits: MappingLimits = MappingLimits()


class ProposedMapping(Contract):
    proposal_id: UUID
    source_system_id: UUID
    schema_fingerprint: Fingerprint
    mapping_version: Literal[1] = 1
    status: Literal["proposed"] = "proposed"
    catalog_digest: Fingerprint
    task_id: UUID
    created_at: AwareDatetime
    target: TargetCandidate
    field: FieldProposal


class RunDiagnostic(Contract):
    code: str
    message: str
    evidence_refs: tuple[UUID, ...] = ()


class MappingRunResult(Contract):
    contract_version: Literal[1] = 1
    run_id: UUID
    source_system_id: UUID
    schema_fingerprint: Fingerprint
    status: Literal["completed", "partial", "failed"]
    proposal_ids: tuple[UUID, ...]
    proposals: tuple[ProposedMapping, ...]
    unresolved_fields: tuple[UnresolvedField, ...]
    diagnostics: tuple[RunDiagnostic, ...]
    provider_run_metadata: dict[str, Any]
