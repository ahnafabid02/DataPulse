"""Partitioned metadata-to-proposal pipeline, exact host-owned scope and provenance."""

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from datapulse.contracts.schema import DatabaseSchema, TableSchema
from datapulse.mapping.catalog import FHIRCatalog
from datapulse.mapping.contracts import (
    FieldRef,
    MappingRunInput,
    MappingRunResult,
    MappingTask,
    ProposedMapping,
    RunDiagnostic,
    UnresolvedField,
    task_output_schema,
)
from datapulse.mapping.discovery import classify, declared_graph
from datapulse.mapping.provider import MappingProvider, ProviderFailure
from datapulse.mapping.validation import OutputRejected, ref_key, validate_output

PROMPT_VERSION = "metadata-mapping-v1"


def proposal_reuse_key(
    request: MappingRunInput,
    schema: DatabaseSchema,
    fields: tuple[FieldRef, ...] | None,
    catalog: FHIRCatalog,
    provider: MappingProvider,
) -> str:
    metadata = provider.metadata()
    payload = {
        "schema": schema.model_dump(mode="json", exclude={"scanned_at"}),
        "scope": request.scope.model_dump(mode="json"),
        "limits": request.limits.model_dump(mode="json"),
        "fields": [f.model_dump(mode="json") for f in fields] if fields is not None else None,
        "catalog_digest": catalog.digest,
        "prompt_version": PROMPT_VERSION,
        "discovery_version": "lexical-v1",
        "validation_version": "proposal-validation-v1",
        "provider": {
            k: metadata.get(k)
            for k in (
                "provider",
                "model",
                "model_digest",
                "runtime_version",
                "context_tokens",
            )
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class RunRejected(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


def _field_table(table: TableSchema, column_name: str) -> TableSchema:
    """A bounded schema projection; never pretend omitted joins were inspected."""
    return table.model_copy(
        update={
            "columns": tuple(c for c in table.columns if c.name == column_name),
            "primary_key": table.primary_key if table.primary_key == (column_name,) else (),
            "foreign_keys": tuple(k for k in table.foreign_keys if k.columns == (column_name,)),
            "unique_constraints": tuple(
                k for k in table.unique_constraints if k.columns == (column_name,)
            ),
            "indexes": tuple(k for k in table.indexes if k.columns == (column_name,)),
            "relationship_hints": (),
        }
    )


class MappingPipeline:
    def __init__(self, catalog: FHIRCatalog, provider: MappingProvider) -> None:
        self.catalog = catalog
        self.provider = provider

    def run(
        self,
        request: MappingRunInput,
        schema: DatabaseSchema,
        fields: tuple[FieldRef, ...] | None = None,
        max_tasks: int = 40,
    ) -> MappingRunResult:
        if (
            request.source_system_id != schema.source_system_id
            or request.database_name != schema.database_name
            or request.schema_fingerprint != schema.structural_fingerprint()
        ):
            raise RunRejected("scan_identity_mismatch")
        tables = {(t.namespace, t.name): t for t in schema.tables}
        scope = {(t.namespace, t.name) for t in request.scope.tables}
        if len(scope) != len(request.scope.tables) or not scope <= tables.keys():
            raise RunRejected("invalid_scope")
        available = {
            (namespace, name, column.name): (table, column)
            for (namespace, name), table in tables.items()
            if (namespace, name) in scope
            for column in table.columns
        }
        selected = tuple(ref_key(f) for f in fields) if fields is not None else tuple(available)
        if (
            len(set(selected)) != len(selected)
            or not set(selected) <= available.keys()
            or not 1 <= max_tasks <= 1000
            or len(selected) > max_tasks
            or not selected
        ):
            raise RunRejected("invalid_field_scope_or_limit")
        proposals, unresolved, diagnostics = [], [], []
        task_digests = []
        task_evidence = []
        attempts = Counter[str]()
        classifications = [classify(tables[key]) for key in sorted(scope)]
        for key in selected:
            table, column = available[key]
            classification = classify(table)
            resources = classification.resources
            if request.scope.domains:
                resources = tuple(r for r in resources if r in request.scope.domains)
            reference = FieldRef(table=classification.table, column=column.name)
            candidates = (
                self.catalog.retrieve(
                    column.name,
                    column.normalized_type,
                    resources,
                    request.limits.max_candidates,
                )
                if resources
                else ()
            )
            if not candidates:
                unresolved.append(
                    UnresolvedField(
                        source_refs=(reference,), reason="No sufficiently supported core candidate"
                    )
                )
                continue
            enum_codes = set(re.findall(r"'([^']*)'", column.native_type))
            operations: set[str] = set()
            for candidate in candidates:
                if column.normalized_type == "string" and any(
                    t in {"date", "dateTime", "instant", "time"} for t in candidate.types
                ):
                    operations.add("date_parse")
                elif candidate.binding and candidate.binding.get("strength") == "required":
                    allowed = self.catalog.binding_codes(candidate.binding.get("valueSet", ""))
                    if enum_codes and allowed is not None and enum_codes <= allowed:
                        operations.add("copy")
                    elif enum_codes and allowed is not None:
                        operations.add("code_map")
                elif candidate.types == ("Reference",):
                    operations.add("reference")
                else:
                    operations.add("copy")
            if not operations:
                unresolved.append(
                    UnresolvedField(
                        source_refs=(reference,),
                        reason="Source value/terminology evidence required",
                    )
                )
                continue
            task_id = uuid4()
            field_tables = (_field_table(table, column.name),)
            allowed_operations = tuple(sorted(operations))
            task = MappingTask(
                task_id=task_id,
                source_system_id=schema.source_system_id,
                database_name=schema.database_name,
                schema_fingerprint=request.schema_fingerprint,
                tables=field_tables,
                candidates=candidates,
                allowed_operations=allowed_operations,
                output_schema=task_output_schema(
                    task_id, field_tables, candidates, allowed_operations
                ),
                max_output_tokens=request.limits.max_tokens,
            )
            # Digests preserve exact task/template identity without generic prompt logs.
            task_digests.append(hashlib.sha256(task.model_dump_json().encode()).hexdigest())
            task_evidence.append(task.model_dump(mode="json"))
            correction = None
            for attempt in range(3):
                try:
                    attempts["provider_calls"] += 1
                    output = self.provider.generate(task, correction)
                    validated = validate_output(task, output, self.catalog)
                    for field in validated.proposals:
                        proposals.append(
                            ProposedMapping(
                                proposal_id=uuid4(),
                                source_system_id=schema.source_system_id,
                                schema_fingerprint=request.schema_fingerprint,
                                catalog_digest=self.catalog.digest,
                                task_id=task.task_id,
                                created_at=datetime.now(UTC),
                                target=next(
                                    c for c in task.candidates if c.id == field.candidate_id
                                ),
                                field=field,
                            )
                        )
                    unresolved.extend(validated.unresolved)
                    break
                except (ProviderFailure, OutputRejected) as error:
                    correction = (
                        error.category if isinstance(error, ProviderFailure) else error.code
                    )
                    attempts[correction] += 1
                    retryable = isinstance(error, OutputRejected) or correction in {
                        "invalid_output",
                        "output_truncated",
                    }
                    if not retryable or attempt == 2:
                        unresolved.append(
                            UnresolvedField(source_refs=(reference,), reason=correction)
                        )
                        diagnostics.append(
                            RunDiagnostic(code=correction, message="Task left unresolved")
                        )
                        break
        diagnostics.append(
            RunDiagnostic(
                code="assembly_review_required",
                message="Field proposals still require full resource and assembly review",
            )
        )
        status: Literal["completed", "partial", "failed"] = (
            "completed" if not unresolved else "partial" if proposals else "failed"
        )
        metadata = self.provider.metadata()
        metadata.update(
            reuse_key=proposal_reuse_key(request, schema, fields, self.catalog, self.provider),
            prompt_template_version=PROMPT_VERSION,
            task_digests=task_digests,
            task_evidence=task_evidence,
            required_fields={
                r: self.catalog.required_elements(r) for c in classifications for r in c.resources
            },
            catalog={"id": "hl7.fhir.r4.core", "version": "4.0.1", "sha256": self.catalog.digest},
            attempts=dict(attempts),
            classifications=[c.model_dump(mode="json") for c in classifications],
            declared_graph=[edge.model_dump(mode="json") for edge in declared_graph(schema)],
        )
        return MappingRunResult(
            run_id=request.run_id,
            source_system_id=schema.source_system_id,
            schema_fingerprint=request.schema_fingerprint,
            status=status,
            proposal_ids=tuple(p.proposal_id for p in proposals),
            proposals=tuple(proposals),
            unresolved_fields=tuple(unresolved),
            diagnostics=tuple(diagnostics),
            provider_run_metadata=json.loads(json.dumps(metadata)),
        )
