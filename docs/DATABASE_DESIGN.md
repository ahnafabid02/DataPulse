# Database design

Hospital revision `hospital_0003` adds immutable `evidence_access` metadata events
and `evidence_observations` with source/scan binding and content digest. Started audit
commits before source reads; successful observation and completed event commit together.
Explicit provisioning upgrades existing M4 registries; old scan/proposal rows remain.
Central migration head is unchanged. Registry owners remain trusted; M5 approval,
assemblies and release tables are not introduced by this prerequisite slice.

## M1 central PostgreSQL

`organizations`: UUID PK, code unique/nonblank, name nonblank, UTC created_at.
`source_systems`: UUID PK, organization FK RESTRICT, code nonblank,
unique(organization_id, code), EHR product/version, vendor (postgresql/mysql/mariadb/
sqlserver/oracle), database_name nonblank, status constraint, UTC created_at.
Index organization FK. No credentials, clinical rows, or identity links in M1.
Alembic revision `0001_foundation` creates these tables; application startup never
creates/migrates schema. Readiness requires the exact configured migration head.

## M2 access and audit

Alembic `0002_access` adds revision (default 1) and retirement timestamps to existing
registrations without dropping their data. Readiness now requires this revision.
`principals` has human/connector kind, unique human username, Argon2id password
hash, unique connector source FK, enabled flag, failed-login counter and lock expiry.
A check constraint enforces human/source binding; password hashes never belong to
connector principals. `role_grants` is keyed by principal/role. Roles are mapped to
permissions in a separate registry and evaluated for every authenticated request.
`credentials` holds principal FK, session/connector kind, unique verification hash,
expiry and revocation time. Raw tokens and passwords are absent from these tables.

`audit_events` contains UUID actor/target/source references, actor kind, action,
UTC occurrence time, server request ID and JSON change metadata. There is no audit
mutation endpoint. Database triggers reject UPDATE/DELETE; PostgreSQL also rejects
TRUNCATE. Dropping the triggers/schema requires privileged operator access and is
not prevented by this demo's bootstrap database owner. Production runtime/migration
role separation remains required. Successful registration/security commands and
audit writes share one transaction; failed/denied requests receive separate redacted
security events. Audit failure prevents successful mutation.

Source changes and key rotation lock their source row. Creating a source locks its
organization to serialize with organization retirement. Bootstrap locks the principal
table on PostgreSQL to serialize first-administrator creation. Retirement retains
rows, principals and historical audit; uniqueness codes are not recycled.

## M3 external source databases

M3 connection/health makes no central schema change or migration. Demo EHR schemas
are created/migrated by their original pinned upstream installers, not DataPulse
ORM or guessed table definitions. Source credentials are hospital-local external
references. Reader grants are restricted to each separate fictional source database.

## Future central tables and constraints

- source_patients: unique(source ID, opaque patient key); demographic snapshots
  live in versioned patient resources, verified identifiers have issuer/provenance.
- global_patients: UUID PK, status, created_at; no destructive copied patient identity.
- identity_links: source_patient FK, global_patient FK, valid_from/to, decision FK;
  partial unique index on source_patient where valid_to IS NULL.
- identity_cases/candidates/decisions: input version/digest, candidate evidence,
  review status and optimistic revision. Unique source patient/input/policy digest
  prevents duplicate pending cases. Reviewer and policy decisions are append-only.
- ingestion_batches: unique(source ID, idempotency key), request digest/status/counts.
- source_resource_versions: JSONB FHIR, unique source/type/record/revision,
  source_patient FK when relevant, mapping/transform versions, timestamps/digests.
- current_resource_pointers: reference latest accepted source version; serializable
  or locked update prevents older replay taking over.
- resource_references: source-namespaced logical reference, resolution status;
  unresolved references held/reconciled rather than guessed.
- provenance_records: FK clinical version + full source envelope + FHIR Provenance.
- validation_results/quarantine: validator/package versions, OperationOutcome,
  protected input and remediation state.
- jobs/outbox: leases, attempts, next_run, deduplication key, terminal errors.
- audit_events: actor/source/action/entity/revision/time/correlation ID; no PHI in
  generic log fields. Sensitive evidence remains in its protected domain store.
- mapping_release_metadata: source/database/release/digest/version descriptors;
  copy for traceability, not central approval authority.

Identity decisions persist link, review disposition and audit in one transaction.
Use row locks and uniqueness constraints for concurrent same-source decisions; use
issuer/identifier locks and uniqueness policy for trusted exact identifier races.
On ambiguous concurrent evidence, retry candidate retrieval and require review.
Clinical versions persist independently of identity case completion.

## Hospital-local store (implemented M4)

Explicit packaged Alembic revisions `hospital_0001` and `hospital_0002` provision
SQLite independently from the central migration head. `schema_snapshots` stores
deduplicated structural JSON by fingerprint; `schema_scans` retains source UUID,
timestamp, snapshot reference and observation-specific comments/defaults/hints.
`mapping_runs` stores source/scan binding, immutable validated proposed/unresolved
results, task evidence and exact-input reuse digest. UPDATE/DELETE triggers protect
these rows against accidental edits; a privileged local file owner can still replace
the file. Run fingerprints must match the bound scan. No source DB credentials,
clinical records, approvals or executable releases are stored by current commands.

Registry opening requires the exact hospital migration head; schema creation occurs
only in the explicit provisioning command. A separate registry belongs to each
hospital deployment. SQLite timeout bounds contention for this single-writer demo;
production multiwriter/durability, backup/encryption and retention remain future
acceptance work. Scan-history transactions commit snapshot/observation together.

## Hospital reviewed registry/outbox (future M5/M6)

Separate SQLite registry per deployed hospital process: schema scans/profiles,
proposal versions, assemblies, reviews, immutable releases, extraction checkpoints
and outbox. Store profile samples only when needed with expiry/access rules. Secrets
are external environment/secret manager references, not columns in this registry.
M4 already implements scan/proposal observations above. Reviewed assemblies/releases,
extraction checkpoints, outbox and WAL/durability testing are future work; multiple
writers require PostgreSQL and a new ADR.

## Persistence strategy and migrations

Use PostgreSQL JSONB for constrained FHIR resources; relational indexes cover source,
patient and time. This does not expose standard FHIR search. Avoid duplicating every
FHIR element into custom tables. A dedicated FHIR server remains behind a port.
Expand/migrate/contract for production changes; review generated migrations. Local
downgrades must never be suggested against real clinical data without a backup and
explicit operational authorization. CI tests upgrade, constraints and downgrade on
disposable databases. SQLite checks are supplementary, not PostgreSQL proof.
