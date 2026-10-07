# Architecture

Status: M1, M1-UI, M2, M3 connection/introspection and M4 are implemented.
Bounded clinical evidence is implemented under ADR-020; extraction cursors,
M5 review/releases and later capabilities remain planned.

ADR-020 authorizes fictional seeds and bounded hospital-local profiling/relationship
evidence before M5. The evidence reader owns declarative source access; immutable
observations and read audit live in the hospital registry. Passing checks grant no
approval. Review/releases remain later slices; see [evidence workflow](EVIDENCE_RUNBOOK.md).

## Deployment and ownership

Use a Python monorepo with two deployment boundaries: a hospital-side service per
source deployment and one central modular application. A hospital may have several
source deployments; mappings are scoped to the exact deployment and database, not
to an EHR product or DB vendor. Central modules initially share a process and
PostgreSQL; they remain separately owned, with explicit interfaces.

```mermaid
flowchart LR
  DB[Hospital database] --> C[Read-only connector]
  C --> S[Normalized schema and relationship graph]
  S --> A[Agent 1 bounded mapping proposals]
  A --> H[Human review]
  H --> R[Hospital mapping registry]
  R --> T[Deterministic transformation and source outbox]
  T --> I[Central authenticated ingestion]
  I --> V[FHIR validation and quarantine]
  V --> E[Agent 2 identity resolution and review]
  E --> P[Source-preserving FHIR storage and provenance]
  P --> Q[Longitudinal query]
```

## Bounded components

- Connector: vendor-specific introspection, bounded profiling, incremental extraction.
  Only this layer resolves local credential references and accesses source databases.
  Implemented M3 adapters provide generic MySQL/MariaDB connection probes and
  metadata-only introspection; profile/extraction remain future ports. Health authenticates
  to one database, checks restricted grants and closes its socket. EHR names occur
  only in demo configuration. See [connection contracts](CONNECTOR_CONTRACTS.md).
- Schema catalog: stable qualified identifiers, immutable scans, fingerprints,
  declared FK graph and persistent local snapshots. Inferred relationships are deferred.
- Mapping proposal pipeline (Agent 1): domain classification, candidate retrieval,
  semantic proposals, confidence evidence, and validation. Does not perform sync.
- FHIR target catalog (implemented M4): verified, cached `hl7.fhir.r4.core#4.0.1`
  StructureDefinitions and terminology bindings shared by all demo sources.
  Source-specific proposals select bounded candidates from this global core catalog;
  BD-Core is outside demo scope (ADR-018).
- Hospital mapping registry/review: immutable mapping versions, approval events,
  approved release snapshots and schema compatibility checks. Hospital SQLite is
  sufficient for a single-node demo; PostgreSQL is the later concurrent option.
  M4 implements immutable scan/proposal-run storage and exact-input proposal reuse
  through explicit hospital Alembic migrations. Reviewed mappings, assemblies,
  approvals and release publication remain M5.
- Hospital runtime: approved release interpreter, extraction checkpoints, durable
  outbox, retries. No model dependency in routine sync.
- Central source administration: organizations, deployments, principal/source binding.
- Central ingestion/validation: authenticated source envelopes, idempotency,
  quarantined failures and processing jobs.
- Central identity (Agent 2): persistent link lookup, candidates, matching evidence,
  conservative policy, review and reversible audited link decisions.
- Central clinical storage/provenance: immutable source resource versions, indexed
  references and provenance. Cannot overwrite another source's record.
- Central query: assembles a longitudinal view through active links; source
  demographics remain distinct and disagreements are displayed.
- Audit: append-only business/security events; separate from operational logs.

## Stack and alternatives

Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, psycopg 3, PostgreSQL 16,
pytest, Ruff, mypy, Docker Compose. Python fits mapping/ML libraries and typed
contracts; FastAPI exposes REST/OpenAPI with little framework overhead. Django is
viable but adds an administrative/ORM framework before the domain stabilizes.
Node/TypeScript would work but splits the initial AI/backend toolchain.

Start with synchronous SQLAlchemy and ordinary `def` API handlers (FastAPI runs
blocking handlers in a thread pool). Durable work runs in a separate worker process
once ingestion exists, using PostgreSQL jobs/outbox with leases and bounded retries.
Do not run durable ingestion or LLM work in request handlers or FastAPI background
tasks. Adopt a broker only if measured load justifies it.

FHIR target: global core R4 4.0.1, with package `hl7.fhir.r4.core#4.0.1`
selected by ADR-018. The official archive checksum/manifest are verified; its manifest
declares no dependencies. ADR-019 records the implemented M4 preparation/proposal slice.
FHIR strategy: constrained R4 JSONB repository behind a storage interface, plus the
official HL7 validator adapter for full profile/terminology validation. It is an
application repository, not a conformant general FHIR REST server. A HAPI FHIR JPA
server is a later storage adapter if standard FHIR search/transactions are needed.
Do not duplicate a full FHIR implementation. See ADR-012 and FHIR strategy.

Local model adapters will support an Ollama-style HTTP provider; remote adapters
can be added. Provider calls accept bounded structured tasks, never DB credentials
or arbitrary executable transformation/SQL. M1 chose no model. M4 includes a
runtime/digest-pinned local Ollama adapter and an evaluated 3B demo model; provider
code remains separate from domain contracts.

An early English React/TypeScript administration shell (M1-UI, ADR-015) is now added
at the user's request. Vite builds static assets into the central package; FastAPI
serves them at `/` with hash navigation. M2 integrates authenticated hospital/source
setup with central PostgreSQL. Browser sessions and connector credentials have
separate identities and permissions; registration writes commit with audit.
Field review, matching and patient-history samples stay in memory. ADR-016 records
the updated UI boundary.
ADR-017 adds the pinned OpenMRS/OpenEMR schema-health demo and hospital-local DB
connection command. No central connectivity endpoint or registration-status change
is introduced. The source compatibility gate precedes connector implementation.

## Operational boundaries

Hospital registry is authoritative for its mappings. Central stores ingestion-time
mapping metadata/digests, not source database secrets. Network delivery is at least
once; durable idempotency and source revisions prevent duplicate clinical writes.
No distributed transaction spans a hospital DB and central DB. No destructive
identity merging. Invalid resources are retained in a restricted quarantine, not
silently discarded. Production authentication, encrypted storage and review roles
are required before any patient endpoints are enabled.

Official references, reviewed 2026-10-07: [FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/),
[SQLAlchemy engines](https://docs.sqlalchemy.org/en/20/core/engines.html),
[Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
[HAPI JPA](https://hapifhir.io/hapi-fhir/docs/server_jpa/get_started.html).
