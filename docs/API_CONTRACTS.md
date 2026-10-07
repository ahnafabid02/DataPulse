# API contracts

## Implemented health and static interface

- `GET /health/live`: 200 `{"status":"ok"}`. No DB dependency.
- `GET /health/ready`: 200 `{"status":"ready"}` only when DB responds and Alembic
  revision is `0002_access`; otherwise 503 `{"status":"not_ready"}`.
  Neither response exposes connection details or patient information.
- `/openapi.json`, `/docs`, `/redoc`: FastAPI-generated implemented M1/M2 API description.

M1-UI adds `GET /` (English application shell), `/assets/*` (build assets) and
`/favicon.svg`. These static routes are omitted from OpenAPI. UI pages use fragment
navigation (`/#hospitals`, `/#fields`, `/#identity`, `/#patients`, `/#help`).
M2 adds the authenticated APIs below. Review/matching/history preview actions stay
in browser memory and never call business endpoints.

Responses include a server-generated UUID `X-Request-ID`; request logs contain only
ID, method, response status and duration.

## Implemented M2 (local fictional demo)

Except login, `/v1` endpoints require authentication. Human sessions use HttpOnly
cookies; connectors supply `Authorization: Bearer <credential>` exclusively.
Browser writes, including login, require `X-DataPulse-Request: 1` and a matching
configured Origin when present. Body maximum is 64 KiB. Extra contract fields are
rejected. Responses use `Cache-Control: no-store`; no secrets appear in errors.
No public signup: use the trusted local operator command in README.

- `POST /v1/auth/login`: username/password -> 200 principal identity and session
  cookie. Identity contains id, kind, username, source_system_id and roles.
- `GET /v1/auth/me`: 200 authenticated identity; invalid/revoked/expired access 401.
- `POST /v1/auth/logout`: human; 204 revokes current browser session.
- `POST /v1/auth/password`: administrator; current_password/new_password -> 204,
  revokes all sessions. New password length 12–128; user must sign in again.
- `GET /v1/organizations`, `GET /v1/sources`: administrator; cursor/limit page
  `{items,next_cursor}`; default 50, max 200. UUID ascending cursors, retired rows
  excluded. Concurrent inserts may require a fresh first-page read.
- `POST /v1/organizations`: administrator; code/name -> 201 organization including
  id, revision, created_at. Code is immutable and unique; duplicate -> 409.
- `PATCH /v1/organizations/{identifier}`: administrator; expected_revision/name ->
  200 updated organization; stale revision -> 409.
- `DELETE /v1/organizations/{identifier}?expected_revision=N`: administrator; 204
  logical retirement; 409 while non-retired source systems still belong to it.
- `POST /v1/sources`: administrator; organization_id, code, ehr_product,
  ehr_version (optional), database_vendor, database_name -> 201
  `{source,credential:{id,token,expires_at}}`. Creates the bound connector principal
  and its first credential atomically. Codes are unique within the hospital.
- `POST /v1/onboarding`: administrator; source details plus exactly one of
  organization `{code,name}` or organization_id -> 201
  `{organization,source,credential}`. All-or-nothing hospital/source setup for UI.
- `GET /v1/sources/{identifier}`: administrator or its bound connector; 200 metadata.
  Connectors requesting another source -> 403, including nonexistent source IDs.
- `PATCH /v1/sources/{identifier}`: administrator; expected_revision, ehr_product,
  ehr_version, database_vendor, database_name, status (registered/suspended) -> 200.
  Suspended revokes credentials. Source code/organization cannot be changed.
- `DELETE /v1/sources/{identifier}?expected_revision=N`: administrator; 204 logical
  retirement, disables principal and revokes all credentials; history retained.
- `POST /v1/sources/{identifier}/credential`: administrator; 200
  `{id,token,expires_at}`; immediately revokes all previous keys. Suspended -> 409.
- `DELETE /v1/sources/{identifier}/credential`: administrator; 204 revokes all keys.
- `GET /v1/audit-events`: administrator with audit_read; `{items,next_cursor}`,
  newest first by timestamp/UUID, limit default 50/max 200. Cursor is the last event
  UUID; subsequent pages continue to older events, excluding new audit-read events.
  Each event includes actor_id/kind, action, target_type/id, source_system_id,
  occurred_at, request_id and change_metadata. Reading audit is itself audited.

Source metadata also includes id, status, revision and created_at. M2 registration
does not activate a database connection. Database names are labels restricted to
letters, numbers, underscores, dots and hyphens; connection URIs/secrets are rejected.
Credential tokens are disclosed only on create/rotate, never read/list/audit APIs.
Lists and source reads never expose password/token hashes. Time values are UTC.

Errors: `{error:{code,message,details:null},request_id}`. 401 invalid authentication;
403 missing permission, wrong source, CSRF protection or suspended source;
404 unavailable registration; 409 duplicate/stale revision/lifecycle conflict;
413 body limit; 422 invalid contract; 429 login throttling (Retry-After);
503 dependency/audit unavailable. No submitted value/DB exception is echoed.

## Planned central APIs (not implemented)

All `/v1` APIs require authenticated principals and scopes. Source identity is
derived from principal registration; request `source_system_id` must match it.
Review commands require human reviewer role, optimistic case/proposal revision and
reason. Pagination uses cursor/limit (default 50, max 200); ISO dates use UTC.

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
