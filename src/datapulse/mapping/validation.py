"""Host-owned semantic checks. These proposals cannot execute or approve mappings."""

import json
import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from datapulse.mapping.catalog import FHIRCatalog, compatible_type
from datapulse.mapping.contracts import (
    ArrayGroup,
    CodeMap,
    Concatenate,
    Conditional,
    Copy,
    DateParse,
    FieldRef,
    LiteralValue,
    MappingTask,
    MappingTaskOutput,
    Reference,
    TransformNode,
    Trim,
)


class OutputRejected(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def ref_key(ref: FieldRef) -> tuple[str, str, str]:
    return ref.table.namespace, ref.table.name, ref.column


def _nodes(node: TransformNode, depth: int = 0) -> list[TransformNode]:
    if depth > 4:
        raise OutputRejected("ast_depth_limit")
    result = [node]
    if isinstance(node, Conditional):
        result.extend(_nodes(node.then, depth + 1))
        result.extend(_nodes(node.otherwise, depth + 1))
    if len(result) > 32:
        raise OutputRejected("ast_node_limit")
    return result


def validate_output(
    task: MappingTask, output: MappingTaskOutput, catalog: FHIRCatalog
) -> MappingTaskOutput:
    if task.task_id != output.task_id:
        raise OutputRejected("task_mismatch")
    columns = {(t.namespace, t.name, c.name): c for t in task.tables for c in t.columns}
    authoritative = {
        c.id: c
        for resource in {c.resource_type for c in task.candidates}
        for c in catalog.candidates(resource)
    }
    candidates = {c.id: c for c in task.candidates}
    if any(authoritative.get(c.id) != c for c in task.candidates):
        raise OutputRejected("catalog_candidate_mismatch")
    evidence = {s.evidence_id for s in task.record_samples} | {task.task_id}
    handled: set[tuple[str, str, str]] = set()
    targets: set[tuple[str, str | None]] = set()
    for proposal in output.proposals:
        if len(proposal.model_dump_json().encode()) > 16000:
            raise OutputRejected("proposal_size_limit")
        if proposal.confidence.calibration_version is not None:
            raise OutputRejected("unverified_calibration")
        candidate = candidates.get(proposal.candidate_id)
        if candidate is None or proposal.target_path != candidate.element_path:
            raise OutputRejected("invalid_candidate_path")
        if not set(proposal.evidence_refs) <= evidence:
            raise OutputRejected("unknown_evidence")
        references = {ref_key(r) for r in proposal.source_refs}
        if not references <= columns.keys():
            raise OutputRejected("unknown_source")
        if (proposal.target_path, proposal.group_id) in targets:
            raise OutputRejected("duplicate_target")
        targets.add((proposal.target_path, proposal.group_id))
        if "[]" in candidate.element_path and not proposal.group_id:
            raise OutputRejected("array_group_required")
        if "[]" not in candidate.element_path and proposal.group_id is not None:
            raise OutputRejected("unexpected_array_group")
        node = proposal.transformation
        if proposal.mapping_type == "direct" and not isinstance(node, Copy):
            raise OutputRejected("mapping_type_mismatch")
        if proposal.mapping_type == "constant" and not isinstance(node, LiteralValue):
            raise OutputRejected("mapping_type_mismatch")
        if proposal.mapping_type == "reference" and not isinstance(node, Reference):
            raise OutputRejected("mapping_type_mismatch")
        actual_refs: set[tuple[str, str, str]] = set()
        for operation in _nodes(node):
            if operation.op not in task.allowed_operations:
                raise OutputRejected("operation_not_allowed")
            refs: list[FieldRef] = []
            if isinstance(operation, Concatenate):
                refs.extend(operation.sources)
            elif not isinstance(operation, LiteralValue):
                refs.append(operation.source)
            actual_refs.update(ref_key(r) for r in refs)
            if any(ref_key(r) not in references for r in refs):
                raise OutputRejected("undeclared_ast_source")
            if isinstance(operation, (Trim, Concatenate)):
                if any(columns[ref_key(r)].normalized_type != "string" for r in refs):
                    raise OutputRejected("transformation_type_mismatch")
                if not any(
                    t in {"string", "code", "id", "uri", "markdown"} for t in candidate.types
                ):
                    raise OutputRejected("target_type_mismatch")
            if isinstance(operation, DateParse):
                if not any(t in {"date", "dateTime", "instant", "time"} for t in candidate.types):
                    raise OutputRejected("target_type_mismatch")
                try:
                    ZoneInfo(operation.timezone)
                    # Check directives without executing any user code.
                    datetime(2001, 2, 3).strftime(operation.format)
                except (ValueError, ZoneInfoNotFoundError):
                    raise OutputRejected("invalid_date_policy") from None
                if "%" not in operation.format:
                    raise OutputRejected("invalid_date_policy")
                directives = re.findall(r"%([a-zA-Z%])", operation.format)
                if any(
                    d not in {"Y", "y", "m", "d", "H", "M", "S", "f", "z", "%"} for d in directives
                ):
                    raise OutputRejected("invalid_date_policy")
            if isinstance(operation, Copy):
                native = columns[ref_key(operation.source)].normalized_type
                if not any(compatible_type(native, t) for t in candidate.types):
                    raise OutputRejected("target_type_mismatch")
                if candidate.types == ("Reference",):
                    raise OutputRejected("explicit_transform_required")
                if native == "string" and any(
                    t in {"date", "dateTime", "instant", "boolean", "Reference"}
                    for t in candidate.types
                ):
                    raise OutputRejected("explicit_transform_required")
                if candidate.binding and candidate.binding.get("strength") == "required":
                    allowed = catalog.binding_codes(candidate.binding.get("valueSet", ""))
                    native_type = columns[ref_key(operation.source)].native_type
                    enum_codes = re.findall(r"'([^']*)'", native_type)
                    if (
                        not native_type.lower().startswith("enum(")
                        or not enum_codes
                        or (allowed is None or not set(enum_codes) <= allowed)
                    ):
                        raise OutputRejected("terminology_source_evidence_required")
            if isinstance(operation, CodeMap):
                if not any(t in {"code", "string", "id", "uri"} for t in candidate.types):
                    raise OutputRejected("target_type_mismatch")
                if any(len(k) > 256 or len(v) > 256 for k, v in operation.values.items()):
                    raise OutputRejected("code_map_size_limit")
            if isinstance(operation, LiteralValue):
                value = operation.value
                if isinstance(value, (dict, list)) or value is None:
                    raise OutputRejected("literal_type_mismatch")
                if isinstance(value, bool):
                    fits = "boolean" in candidate.types
                elif isinstance(value, int):
                    fits = any(
                        t in {"integer", "positiveInt", "unsignedInt", "decimal"}
                        for t in candidate.types
                    )
                    if "positiveInt" in candidate.types and value <= 0:
                        fits = False
                    if "unsignedInt" in candidate.types and value < 0:
                        fits = False
                    if any(t in {"integer", "positiveInt", "unsignedInt"} for t in candidate.types):
                        fits = fits and -(2**31) <= value < 2**31
                elif isinstance(value, float):
                    fits = "decimal" in candidate.types and math.isfinite(value)
                else:
                    fits = any(
                        t in {"string", "code", "id", "uri", "url", "canonical", "markdown"}
                        for t in candidate.types
                    )
                if not fits or len(json.dumps(value)) > 1000:
                    raise OutputRejected("literal_type_mismatch")
            if isinstance(operation, Reference):
                if candidate.types != ("Reference",):
                    raise OutputRejected("target_type_mismatch")
                # Assembly/reference resolution is M5/M6: declared source key evidence
                # is required even to retain a reference recipe proposal in M4.
                local_table = next(
                    t
                    for t in task.tables
                    if (t.namespace, t.name)
                    == (operation.source.table.namespace, operation.source.table.name)
                )
                if not any(
                    operation.source.column in fk.columns for fk in local_table.foreign_keys
                ):
                    raise OutputRejected("reference_key_evidence_required")
                catalog.candidates(operation.target_resource)
                allowed_targets = {
                    url.rsplit("/", 1)[-1].split("|", 1)[0] for url in candidate.target_profiles
                }
                if (
                    allowed_targets
                    and "Resource" not in allowed_targets
                    and (operation.target_resource not in allowed_targets)
                ):
                    raise OutputRejected("reference_target_mismatch")
            if isinstance(operation, ArrayGroup) and operation.group_id != proposal.group_id:
                raise OutputRejected("array_group_mismatch")
            if isinstance(operation, (CodeMap, LiteralValue)) and candidate.binding:
                if candidate.binding.get("strength") == "required":
                    values = (
                        tuple(operation.values.values())
                        if isinstance(operation, CodeMap)
                        else (operation.value,)
                    )
                    allowed = catalog.binding_codes(candidate.binding.get("valueSet", ""))
                    if allowed is None or any(v not in allowed for v in values):
                        raise OutputRejected("terminology_unverified")
        if actual_refs != references:
            raise OutputRejected("unused_source_reference")
        if handled & references:
            raise OutputRejected("duplicate_source_disposition")
        handled.update(references)
    for unresolved in output.unresolved:
        unresolved_keys = {ref_key(r) for r in unresolved.source_refs}
        if not unresolved_keys <= columns.keys() or unresolved_keys & handled:
            raise OutputRejected("invalid_unresolved_source")
        handled.update(unresolved_keys)
    if handled != columns.keys():
        raise OutputRejected("incomplete_source_disposition")
    return output
