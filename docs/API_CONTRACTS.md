# API contracts

## Implemented M1

- `GET /health/live`: 200 `{"status":"ok"}`. No DB dependency.
- `GET /health/ready`: 200 `{"status":"ready"}` only when DB responds and Alembic
  revision is `0001_foundation`; otherwise 503 `{"status":"not_ready"}`.
  Neither response exposes connection details or patient information.
- `/openapi.json`, `/docs`, `/redoc`: FastAPI-generated health-only API description.

M1-UI adds `GET /` (English application shell), `/assets/*` (build assets) and
`/favicon.svg`. These static routes are omitted from OpenAPI. UI pages use fragment
navigation (`/#hospitals`, `/#fields`, `/#identity`, `/#patients`, `/#help`).
No new business API exists; all preview actions stay in browser memory.

Responses include a server-generated UUID `X-Request-ID`; request logs contain only
ID, method, response status and duration. M1 has no protected business endpoints.

## Planned central APIs (not implemented)

All `/v1` APIs require authenticated principals and scopes. Source identity is
derived from principal registration; request `source_system_id` must match it.
Review commands require human reviewer role, optimistic case/proposal revision and
reason. Pagination uses cursor/limit (default 50, max 200); ISO dates use UTC.

- `POST /v1/organizations`: admin; code/name -> 201 organization.
- `POST /v1/sources`: admin; organization ID, code, product/version, vendor,
  database name -> 201 source. Credential fields rejected.
- `GET /v1/sources/{id}`: authorized source/admin -> status/config metadata.
- `POST /v1/ingestion-batches`: source-ingest scope, `Idempotency-Key` header,
  IngestionEnvelope below -> 202 receipt `{batch_id,status:"accepted"}`.
  Repeated identical key/digest -> same receipt; conflicting digest -> 409.
- `GET /v1/ingestion-batches/{id}`: owner/admin -> status/counts/quarantine references.
- `GET /v1/identity-cases`: reviewer -> candidate evidence, protected field context.
- `POST /v1/identity-cases/{id}/decision`: reviewer -> approve_link/reject_candidate/
  create_new with expected_revision, candidate ID as needed, reason -> decision/link.
- `POST /v1/identity-links/{id}/close`: reviewer -> reason/expected_revision ->
  closed link plus audit. Relinking must create a new reviewed decision.
- `GET /v1/patients/{global_id}/history`: clinical-reader scope -> cursor page of
  sourced resource versions, active links and provenance. Internal global ID is not
  asserted to be an official national Health ID.

IngestionEnvelope v1: `{contract_version:1, source_system_id:UUID,
source_database:string, mapping_release:{version:int,digest:string},
transformation_version:string, entries:IngestionEntry[]}`.
Entry: `{source_patient_id:string|null, source_record:{namespace:string,table:string,
key:string,revision:string}, resource_assembly_id:UUID,resource_assembly_version:int,
source_recorded_at:datetime|null, resource:object}`. Resource is
valid R4 JSON; non-patient resource keys may be null. Future batch maximum is 100
entries/5 MiB, configurable. Do not infer source effective time from ingestion time.
References and Patient namespace binding are validated before clinical publication.
The source connector declares revision ordering; opaque revision strings are never
lexicographically interpreted as an ordering. Composite source record keys use
canonical JSON encoding, not ambiguous delimiter concatenation.

Receipt status: accepted/processing/completed/partial/quarantined/failed. HTTP 202
means durable receipt only, not validation success or identity linkage.

Error shape (future): `{error:{code:string,message:string,details:object|null},
request_id:UUID}` with redacted details. 401 invalid token; 403 wrong scope/source;
409 idempotency/revision conflict; 413 bound exceeded; 422 malformed contract;
429 rate limit with Retry-After; 503 temporary dependency failure. FHIR validator
issues appear in stored OperationOutcome, not as an assertion of FHIR REST semantics.

## Planned hospital APIs (not implemented)

Local authenticated admin/reviewer access:
`POST /v1/schema-scans` -> asynchronous scan ID;
`GET /v1/schema-scans/{id}` -> normalized schema/status;
`POST /v1/mapping-runs` -> scoped Agent 1 job;
`GET /v1/mapping-proposals` -> bounded proposals;
`POST /v1/mapping-proposals/{id}/reviews` -> decision against exact version/digest;
`POST /v1/mapping-releases` -> immutable validated approved release;
`POST /v1/sync-runs` -> deterministic run using explicit release.
These routes are not central routes. The review UI reaches a hospital gateway or
explicit authorized proxy; central approval copies are not authoritative.

Agent/model internal contracts are defined in the two agent documents. Unimplemented
routes must not be added as pretend successful stubs in OpenAPI.
