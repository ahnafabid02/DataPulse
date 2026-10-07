# Agent 1: hospital mapping

M4 implements the metadata-only proposal pipeline and typed v1 envelopes under
ADR-019. Clinical profiling/extraction, reviewed assembly/releases and deterministic
runtime remain later work. See [local workflow](M4_RUNBOOK.md). ADR-020 now adds
standalone bounded column/relationship evidence; current M4 tasks remain metadata-only
until explicit evidence integration. Human semantic review and complete clinical
coverage are required; Patient is the first release slice, not the final scope.

## Connector boundary

`DatabaseConnector` M1 protocol: `introspect(source_system_id:UUID) -> DatabaseSchema`,
`profile_columns(table:TableRef, columns:tuple[str,...], limit:int) -> ColumnProfile[]`,
`extract_batch(request:ExtractionRequest) -> ExtractedBatch`, `close() -> None`.
The concrete M3 `SchemaScanner` implements introspection alone; it does not pretend
to implement the profile/extraction methods of this broader future protocol.
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

The demo target catalog is `hl7.fhir.r4.core#4.0.1` (ADR-018). BD-Core is outside
demo scope. M4 verifies/caches the package and dependencies before candidate use;
the host binds run targets and candidate provenance to those exact versions.

MappingRunInput: `{contract_version:1, run_id:UUID, source_system_id:UUID,
database_name:string, schema_fingerprint:sha256, schema_scan_id:UUID,
scope:{tables:TableRef[],domains:string[]}, target:{fhir_version:"4.0.1",
packages:[{id:string,version:string}]}, limits:{max_tables_per_task:int,
max_columns_per_task:int,max_sample_rows:int,max_candidates:int,max_tokens:int}}`.
Initial maxima: 8 tables, 40 columns, 20 rows, 12 candidates, configured model token
budget. Partition further when bounds exceed. Full schema never becomes one prompt.
Implemented runs partition selected fields into one-field tasks. Default candidates
are 6 (ceiling 12), output budget 2,048 tokens and CLI field limit 40. Current tasks
have empty profile/sample arrays; no clinical rows are read. Declaration-only graph
and lexical classification evidence are saved separately from each bounded task.

Demo run target: `{fhir_version:"4.0.1",
packages:[{id:"hl7.fhir.r4.core",version:"4.0.1"}]}`. Verified package dependencies
are pinned in the catalog/release metadata. Host validation rejects a target or
candidate outside the accepted core catalog; the provider cannot add packages or
switch FHIR versions. Optional profile fields do not authorize BD-Core or another
implementation guide in this demo.

Stages:
1. Introspect/serialize deterministic schema; build declared FK adjacency. Inferred
   edges are deferred; absent constraints are not guessed. No graph database.
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
types:string[], min:int, max:string, description:string, binding:object|null,
target_profiles:string[]}`. Reference targets retain official `targetProfile` metadata.
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

Implemented validation rejects unknown sources/evidence, forged candidate/path pairs,
unsupported ASTs/types, unsafe repetition/reference recipes and unverified required
terminology. Native enum values can establish direct code evidence; otherwise source
value evidence is required. Root required fields are retained as diagnostics; complete
FHIR resources/joins cannot be certified by a one-field proposal. Step 7 and full
assembly validation remain M5/M6, and M4 stores only `proposed` versions. Catalog task
evidence uses the host-generated task UUID, with its complete bounded envelope retained
in the local run. Model calibration claims are rejected in this uncalibrated demo.

Run output: `{run_id,source_system_id,schema_fingerprint,status:
completed|partial|failed,proposal_ids:UUID[],unresolved_fields:FieldRef[],
diagnostics:[{code,message,evidence_refs:UUID[]}],provider_run_metadata}`.
Only validated proposals persist; completion never implies approval or sync readiness.
Provider metadata includes model/version, prompt-template version and content digest;
sensitive prompt bodies are excluded from generic telemetry.

## Transformations and runtime

Implemented provider port: `generate(task:MappingTask, correction_code:null|string)
-> MappingTaskOutput`, plus bounded provenance metadata; transport
errors distinguish timeout/unavailable/invalid_output without sensitive response
bodies. A local HTTP or remote adapter has the same contract and bounded timeout.
A local Ollama adapter is implemented; remote adapters remain future work. Host-only
correction codes carry no rejected model bodies. Exact runtime/model pins and socket/
total deadlines precede inference; proxy/redirect/cloud forwarding are rejected.

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
