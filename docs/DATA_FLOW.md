# Data flow

## Implemented source connection slice

M2 authenticates and saves hospital/source registration metadata. The first M3
slice separately initializes two pinned fictional EHR databases and provisions local
SELECT-only accounts. A hospital-local probe resolves its bound credential reference,
authenticates, checks the configured database/vendor and restricted grants, reports
redacted health metadata and closes resources. It neither updates central source
status. ADR-019 now adds separate metadata scans and M4 proposal preparation: scan
the configured DB, save immutable observations, derive bounded core FHIR candidates,
validate local model proposals and retain unapproved results. No clinical rows are
sampled/extracted by M4. ADR-020 separately reads bounded selected column values
and relationship metrics, recording access before source reads and immutable
observations afterward. Coverage inventories retain every scanned field awaiting
review. Synchronization and human approval below remain planned.

## Onboarding and Agent 1

1. Central registers organization/source and binds a source principal. Hospital
   configures its own read-only credential reference; secrets never travel centrally.
2. Connector scans allowlisted catalogs into DatabaseSchema v1. Immutable scan and
   fingerprint are saved hospital-side. Profiling is separate and bounded.
3. Declared FK graph and evidence-labelled inferred edges support domain discovery.
   Table classification yields a small set of resource candidates. The demo FHIR
   catalog derives valid nested elements, types, cardinalities and bindings from
   verified `hl7.fhir.r4.core#4.0.1` StructureDefinitions (ADR-018). Both demo sources
   use this core target; their proposals remain source-specific. BD-Core is outside
   demo scope. Package verification and catalog retrieval are implemented in M4.
4. Agent 1 proposes assembly recipes, field paths and safe transformations using
   only task-relevant table neighborhoods and samples. All proposals are validated.
5. Human review approves exact proposal versions/assembly digest. A complete release
   is validated and published atomically in the local registry.

Steps 1-3 and bounded field proposals in step 4 are implemented. The local registry
retains source/scan/task/catalog/model evidence and reuses exact compatible proposal
inputs. Repeated schema observations remain distinct. Full assembly recipes, step 5,
and the synchronization flow require M5/M6. Proposal reuse never implies approval.

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

M1 establishes configuration, relational foundation, schema contracts and central
health probes. M2 implements registration/access/audit. The first M3 slice implements
source database connection health and metadata-only scans. M4 adds catalog/proposal
preparation and local history. Reviewed releases and synchronization remain deferred.
