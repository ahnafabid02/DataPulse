# Database design

## M1 central PostgreSQL

`organizations`: UUID PK, code unique/nonblank, name nonblank, UTC created_at.
`source_systems`: UUID PK, organization FK RESTRICT, code nonblank,
unique(organization_id, code), EHR product/version, vendor (postgresql/mysql/mariadb/
sqlserver/oracle), database_name nonblank, status constraint, UTC created_at.
Index organization FK. No credentials, clinical rows, or identity links in M1.
Alembic revision `0001_foundation` creates these tables; application startup never
creates/migrates schema. Readiness requires the exact configured migration head.

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

## Hospital-local store (future)

Separate SQLite registry per deployed hospital process: schema scans/profiles,
proposal versions, assemblies, reviews, immutable releases, extraction checkpoints
and outbox. Store profile samples only when needed with expiry/access rules. Secrets
are external environment/secret manager references, not columns in this registry.
Enforce local transactions/WAL; multiple writers require PostgreSQL and a new ADR.

## Persistence strategy and migrations

Use PostgreSQL JSONB for constrained FHIR resources; relational indexes cover source,
patient and time. This does not expose standard FHIR search. Avoid duplicating every
FHIR element into custom tables. A dedicated FHIR server remains behind a port.
Expand/migrate/contract for production changes; review generated migrations. Local
downgrades must never be suggested against real clinical data without a backup and
explicit operational authorization. CI tests upgrade, constraints and downgrade on
disposable databases. SQLite checks are supplementary, not PostgreSQL proof.
