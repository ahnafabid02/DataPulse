"""Deterministic declared-FK graph and evidence-labelled lexical classification."""

import re

from datapulse.contracts.schema import Contract, DatabaseSchema, TableRef, TableSchema


class DeclaredEdge(Contract):
    source: TableRef
    target: TableRef
    constraint: str
    columns: tuple[str, ...]
    referenced_columns: tuple[str, ...]
    target_in_scan: bool


class Classification(Contract):
    table: TableRef
    resources: tuple[str, ...]
    status: str
    evidence: tuple[str, ...]
    method: str = "lexical-v1"


def declared_graph(schema: DatabaseSchema) -> tuple[DeclaredEdge, ...]:
    tables = {(t.namespace, t.name) for t in schema.tables}
    return tuple(
        DeclaredEdge(
            source=TableRef(namespace=t.namespace, name=t.name),
            target=fk.referenced_table,
            constraint=fk.name,
            columns=fk.columns,
            referenced_columns=fk.referenced_columns,
            target_in_scan=(fk.referenced_table.namespace, fk.referenced_table.name) in tables,
        )
        for t in schema.tables
        for fk in t.foreign_keys
    )


def classify(table: TableSchema) -> Classification:
    words = set(re.findall(r"[a-z0-9]+", table.name.lower()))
    columns = set(re.findall(r"[a-z0-9]+", " ".join(c.name for c in table.columns).lower()))
    rules = {
        "Patient": {"patient", "patients", "demographics"},
        "Encounter": {"encounter", "encounters", "visit", "visits"},
        "Observation": {"observation", "observations", "obs", "vitals"},
        "Organization": {"organization", "organizations", "facility", "hospital"},
        "Provenance": {"provenance", "audit"},
    }
    matches = []
    evidence = []
    for resource, labels in rules.items():
        hit = sorted(words & labels)
        if hit:
            matches.append(resource)
            evidence.append(f"table_name:{','.join(hit)}")
    if not matches and {"birthdate", "gender"} <= columns:
        matches.append("Patient")
        evidence.append("columns:birthdate,gender")
    return Classification(
        table=TableRef(namespace=table.namespace, name=table.name),
        resources=tuple(matches),
        status="candidate" if matches else "uncertain",
        evidence=tuple(evidence or ["No sufficient lexical evidence"]),
    )
