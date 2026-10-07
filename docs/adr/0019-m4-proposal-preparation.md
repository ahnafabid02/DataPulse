# ADR-019: Hospital-local schema registry and M4 mapping proposals

Accepted 2026-10-07 at the user's explicit request to implement complete M4 after
agreeing the introspection and registry scope. This expands ADR-017's connection
boundary to metadata-only scans, a persistent hospital-local registry and the M4
catalog/proposal pipeline. M3 profiling, clinical extraction and drift monitoring,
and M5-M9 review/runtime/identity/UI capabilities remain deferred.

Scan base tables in the configured database, optionally narrowing to a table
allowlist; enforce metadata counts, bytes and deadlines, and reject inconsistent
observations. Capture declared keys only. Use MariaDB's SELECT-visible
KEY_COLUMN_USAGE rather than TABLE_CONSTRAINTS, which hides rows from SELECT-only
accounts. Credentials and source access remain in generic vendor adapters.

Provision a separate hospital SQLite registry explicitly through packaged Alembic
migrations. Keep immutable scan observations and deduplicate structural snapshots;
preserve comments/defaults separately per scan because they are excluded from the
structural fingerprint. Save validated, unapproved proposal runs with exact task
evidence and catalog/model/template versions. Reuse successful or partial proposal
runs only for an exact source, semantic input, catalog, model and policy digest;
`--force` creates a new run. Reuse never grants approval. M5 owns reviewed mappings,
assemblies and executable releases; schema equality alone cannot approve reuse.

Use global `hl7.fhir.r4.core#4.0.1` (ADR-018), verified by the recorded archive
checksum and manifest. Host-derived candidates, qualified fields, operation subsets
and output schemas bound the replaceable provider. The local Ollama adapter checks
runtime version/model digest, rejects cloud forwarding and redirects, disables
ambient proxies and bounds input/output/deadlines. A maximum of two correction
attempts follows the initial request; unresolved evidence stays unresolved. No
patient sampling, model credentials, arbitrary SQL, automatic approval or routine
synchronization is introduced.
