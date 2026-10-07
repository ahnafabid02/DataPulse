# Agent 1: hospital mapping

Design contract v1; implementation begins at M4, not M1.

## Connector boundary

`DatabaseConnector` M1 protocol: `introspect(source_system_id:UUID) -> DatabaseSchema`,
`profile_columns(table:TableRef, columns:tuple[str,...], limit:int) -> ColumnProfile[]`,
`extract_batch(request:ExtractionRequest) -> ExtractedBatch`, `close() -> None`.
Concrete connectors validate namespace/table/columns against a fresh allowlisted
catalog, quote identifiers with vendor APIs, parameterize values and impose bounds.
No raw SQL method exists. Credential resolution is outside model/pipeline contracts.
Use context-managed lifecycle around calls; close releases connector resources.

ExtractionRequest defines table, projected columns, ordered stable key_columns,
batch_size (1..1000), opaque cursor and optional updated-since watermark. Request
is declarative and validated; extraction/join recipe execution is a later port.
ExtractedBatch has rows, next_cursor, schema_fingerprint and source_snapshot token.
Supported vendor adapter must explicitly define consistent snapshot/revision behavior.
Unsupported tables without stable extraction keys cannot silently synchronize.

## Pipeline and bounded contracts

MappingRunInput: `{contract_version:1, run_id:UUID, source_system_id:UUID,
database_name:string, schema_fingerprint:sha256, schema_scan_id:UUID,
scope:{tables:TableRef[],domains:string[]}, target:{fhir_version:"4.0.1",
packages:[{id:string,version:string}]}, limits:{max_tables_per_task:int,
max_columns_per_task:int,max_sample_rows:int,max_candidates:int,max_tokens:int}}`.
Initial maxima: 8 tables, 40 columns, 20 rows, 12 candidates, configured model token
budget. Partition further when bounds exceed. Full schema never becomes one prompt.

Stages:
1. Introspect/serialize deterministic schema; build FK adjacency plus separately
   labelled inferred edges. No mandatory graph database.
2. Lexical/domain classification locates patient/encounter/clinical tables. Persist
   uncertain classifications with evidence; graph neighborhoods bound join exploration.
3. Retrieve FHIR candidates from pinned StructureDefinitions and descriptions using
   lexical search and datatype/cardinality filters; add embeddings only if evaluated.
4. Create `MappingTask` (exact v1 envelope): `{contract_version:1, task_id:UUID,
source_system_id:UUID, database_name:string, schema_fingerprint:sha256,
tables:TableSchema[], profiles:ColumnProfile[], record_samples:RecordSample[],
candidates:TargetCandidate[], allowed_operations:string[], output_schema:object,
max_output_tokens:int}`. RecordSample: `{evidence_id:UUID, table:TableRef,
values:object}`; values are bounded connector-selected column JSON values, not raw
query results supplied by a model. TargetCandidate: `{id:string, resource_type:string,
profile_url:string|null, profile_version:string|null, element_path:string,
types:string[], min:int, max:string, description:string, binding:object|null}`.
Host derives candidates from pinned FHIR metadata. Provider does not receive
unrestricted schema tools. `FieldRef={table:TableRef,column:string}` refers to the
task's database; native datatype and join context are resolved from the host scan.
5. Provider returns `MappingTaskOutput`: `{task_id:UUID, proposals:FieldProposal[],
unresolved:[{source_refs:FieldRef[],reason:string}]}`. FieldProposal contains source_refs,
`candidate_id:string`, `target_path:string`, `group_id:string|null`,
`mapping_type:direct|transformed|constant|reference`, `transformation:TransformNode`,
`confidence:{score:number|null,method:string,calibration_version:string|null,reasons:string[]}`,
`evidence_refs:UUID[]`, `rationale:string`. Evidence references must exist in the
task's sample/profile/catalog evidence set. Host supplies authoritative source/version/time/status;
model cannot approve, forge reviewer or select arbitrary targets outside candidates.
6. Validate JSON Schema, source existence, candidate ID/path, types, AST allowlist,
   terminology values, required FHIR fields, repetition/join semantics. Invalid output
   cannot enter registry; bounded correction retry (max 2), then unresolved result.
7. Human reviews fields and full assembly; approved versions form a validated release.

Run output: `{run_id,source_system_id,schema_fingerprint,status:
completed|partial|failed,proposal_ids:UUID[],unresolved_fields:FieldRef[],
diagnostics:[{code,message,evidence_refs:UUID[]}],provider_run_metadata}`.
Only validated proposals persist; completion never implies approval or sync readiness.
Provider metadata includes model/version, prompt-template version and content digest;
sensitive prompt bodies are excluded from generic telemetry.

## Transformations and runtime

Provider port (future): `generate(task:MappingTask) -> MappingTaskOutput`; transport
errors distinguish timeout/unavailable/invalid_output without sensitive response
bodies. A local HTTP or remote adapter has the same contract and bounded timeout.

Versioned allowlisted AST operations: copy, literal, trim, date_parse with explicit
format/timezone, code_map, concatenate, conditional, reference and array grouping.
TransformNode is a discriminated JSON object with `op` and op-specific fields, e.g.
`{op:"code_map",source:FieldRef,values:{M:"male",F:"female",U:"unknown"},
on_unmapped:"quarantine"}`. The complete executable grammar and transform null policies
are a deliverable of M5/M6; proposals must not be executable before that grammar and
assembly validation exist. No eval, Python snippets, shell, arbitrary SQL or model execution at runtime.
Unknown values must trigger an explicit missing/unknown/quarantine policy; never
silently map every unknown sex code to a known gender.

Example proposal: source `patient_master.sex_cd` -> `Patient.gender`, code_map
`{"M":"male","F":"female","U":"unknown"}` with `on_unmapped:"quarantine"`.
`pat_name` -> `name[].text` is plausible with evidence; splitting it into family and
given requires reviewed locale-specific semantics, not blind space splitting.

Release validation checks every required element, reference recipe, join cardinality
and null/unmapped policy using controlled records. Runtime loads approved immutable
release/digest, verifies dependency compatibility and transforms deterministically.
Schema changes, rejected/unresolved fields, observed drift and explicit reanalysis
re-enter mapping; routine synchronization never calls the model.

Confidence policies are configurable and calibrated on labelled examples. Scores
prioritize review and explain uncertainty; no arbitrary auto-approval threshold.
Test novel schemas, renamed columns, missing FKs, many-to-many joins, repeated arrays,
ambiguous dates/codes, partial model output and drift before enabling sync.
