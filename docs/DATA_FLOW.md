# Data flow

## Onboarding and Agent 1

1. Central registers organization/source and binds a source principal. Hospital
   configures its own read-only credential reference; secrets never travel centrally.
2. Connector scans allowlisted catalogs into DatabaseSchema v1. Immutable scan and
   fingerprint are saved hospital-side. Profiling is separate and bounded.
3. Declared FK graph and evidence-labelled inferred edges support domain discovery.
   Table classification yields a small set of resource candidates. The FHIR catalog
   retrieves valid nested elements, types, cardinalities, bindings and profiles.
4. Agent 1 proposes assembly recipes, field paths and safe transformations using
   only task-relevant table neighborhoods and samples. All proposals are validated.
5. Human review approves exact proposal versions/assembly digest. A complete release
   is validated and published atomically in the local registry.

## Synchronization and central ingest

1. Connector extracts a bounded batch under a checkpoint. A reviewed assembly and
   deterministic interpreter create R4 resources and provenance envelopes.
2. Durable local outbox is committed before advancing the extraction checkpoint.
   Delivery retries use the same batch key. Source updates carry monotonically ordered
   source revisions or explicitly defined snapshot sequence; deletes use tombstones.
3. Central authenticates source ownership, checks payload size/idempotency, saves
   receipt and jobs transactionally, returns 202. It does not match patients inline.
4. Worker validates syntax, R4/profile/terminology and references. Invalid entries
   enter quarantine with actionable OperationOutcome; other entries are not silently
   dropped. Batch status exposes partial/quarantined counts. Raw quarantine access
   is restricted and retention-controlled.
5. Patient resources enter identity resolution. A valid stored link short-circuits
   matching, except material verified-identifier conflicts open a review and hold
   affected new associations. Pending records remain associated to source identity.
6. Valid source resource versions and provenance persist; query joins active source
   links to build global history. Non-patient resources are stored without a patient
   key and references resolve within their source namespace.

## Recovery and evolution

Central unique batch key is (source ID, idempotency key); duplicate identical
digest returns the receipt, different digest returns 409. Unique clinical version
key is (source ID, resource type, source record key, source revision).
Unexpected older revisions cannot replace a newer current pointer.
Retries use exponential backoff with jitter, limits and dead-letter review. No
automatic retry of auth failures, conflicts or persistent validation failures.
FHIR storage writes and internal metadata initially share a central transaction.
If HAPI is adopted, use an outbox and reconciler rather than claiming atomic cross-DB
writes. Job leases allow crash recovery and idempotent reprocessing.

Schema drift pauses only affected assemblies. Previously approved unaffected
dependencies can continue after deterministic compatibility checking. New or changed
dependencies re-enter proposal/review; all replay uses explicit release versions.
Relinking changes a query association, not clinical payload history. Correction
events must be visible and auditable.

M1 implements none of these business flows; it establishes configuration, relational
foundation, connector/schema contracts and health probes.
