# Implementation roadmap

Complete one milestone at a time; read its contracts before coding. Do not treat a
test suite passing as clinical approval or a foundation as a working full demo.

## Phase 0 — Source of truth
Create all requested documents, ADRs and repository layout. Review scope, ownership,
versioning, identity and provenance across documents before M1.

## M1 — Foundation (this revision)
Python package/config, FastAPI app factory, JSON request logs, liveness/readiness,
PostgreSQL Compose and separate migrations job, organization/source ORM + first
migration, normalized schema model/fingerprint and connector protocol, CI and tests.
No business endpoint or concrete EHR connector.
Acceptance: local test/lint/type checks pass; migration upgrade/constraints/downgrade
tested; readiness reports DB/revision failures safely; PostgreSQL integration and
container startup verified when environment permits, explicitly reported otherwise.

## M1-UI — Friendly workspace (added at user request before M2)
English responsive administration shell, guided hospital setup, field explanations,
conservative sample identity review, source-preserving patient timeline and help.
Serve built assets from the same central application; live health probes are real,
all clinical/hospital content is explicitly fictional and session-only.
Acceptance: keyboard/mobile navigation, accessible forms/dialog, clear preview labels,
no unconfirmed identities in combined history, live health failures explained,
frontend interaction/build checks, backend static-serving tests and browser review.
No unauthenticated business writes or fake successful connection endpoints.

## M2 — Source onboarding and access control (recommended next)
Implement authenticated organization/source registration/read APIs, source principal
binding, rotating credential references, admin/source scopes and append-only audit.
Acceptance: unauthorized/wrong-source access denied, duplicate source constraint,
credential redaction, migration tests, OpenAPI contracts and PostgreSQL API tests.
Do not implement schema introspection or model calls in M2.

## M3 — Source connector and two demo databases
Pin verified upstream OpenMRS/OpenEMR images/compose commits and matching DB versions;
deploy controlled data in separate source databases; implement necessary MySQL/
MariaDB connector(s), allowlisted introspection/profiling/extraction and schema drift.
Acceptance: compare genuinely different schemas, keys/indexes/type edge cases,
read-only permissions, sampling bounds, stable cursors and reproducible controlled data.
Exact demo versions remain an explicit research/deployment gate, not guessed in M1.

## M4 — FHIR catalog and mapping proposal contracts
Verify/cache pinned R4 and BD-Core packages/checksums/dependencies; normalized FK
graph, table domain classification, bounded candidate retrieval; provider abstraction
and validated task output with local adapter. Acceptance: bounded prompts, no secrets
or arbitrary SQL, invalid JSON/candidate/path/AST rejected, ambiguous fields retained.
Evaluate model accuracy/hardware; do not auto-approve mappings.

## M5 — Hospital registry and review
Immutable mappings/assemblies/releases, human approval tied to digest, lifecycle and
schema compatibility checks, hospital registry migrations. Acceptance: edits cannot
reuse approval, stale/concurrent review blocked, repeat grouping/join semantics tested.

## M6 — Deterministic transform and central ingestion
Versioned AST interpreter, source outbox/checkpoints, idempotent authenticated durable
ingestion, official validator, JSONB source versions/provenance/quarantine and jobs.
Acceptance: reviewed synthetic Patient/Encounter/Observation slice validates, replay
deduplicates, unknown codes and bad refs quarantine, source revisions remain immutable,
routine sync performs zero model calls. Worker failures/retries tested.

## M7 — Conservative central identity
Source/global/link/case migrations, layered matching, evidence and human review,
stored-link fast path, conflict hold, unlink/relink history. Acceptance: adversarial
false-positive tests, concurrency/replay, rich reasoning is advisory only, pending
records never appear under a guessed global identity.

## M8 — Longitudinal API and administration UI
Stabilize history/review APIs first, then React onboarding/mapping/identity/history UI.
Acceptance: chronological patient view retains source/provenance and discrepancies,
roles enforced, review uses exact versions, revoked links reflected in projections.

## M9 — Reproducible end-to-end demo and operational hardening
OpenMRS and OpenEMR independently analyzed/reviewed/transformed; same-person and
different-person fixtures demonstrate central review/linking and persistent fast path.
Acceptance: complete reset/seed/demo guide, E2E validation/provenance, drift and replay
tests, measured review accuracy, backup/recovery exercise, realistic limitation report.

No production clinical deployment until access, retention, governance, restore,
clinical review and interoperability acceptance gates are completed.
