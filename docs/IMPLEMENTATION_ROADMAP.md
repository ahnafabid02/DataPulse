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

## M2 — Source onboarding and access control (implemented)
Implement authenticated organization/source registration/read APIs, source principal
binding, rotating credential references, admin/source scopes and append-only audit.
Acceptance: unauthorized/wrong-source access denied, duplicate source constraint,
credential redaction, migration tests, OpenAPI contracts and PostgreSQL API tests.
User-confirmed extension: integrate the friendly hospital setup UI with sign-in,
persistent fictional registrations, one connector identity per source, credential
rotation/revocation, revision-checked updates/retirement and activity viewing.
Bootstrap one administrator using an interactive operator command. Future reviewer/
reader permissions are separate from authentication. Passwords and tokens are hashed;
successful mutations and audit commit atomically. Audit is protected by DB triggers.
Do not implement hospital DB connectivity, introspection, extraction, Agent 1,
Agent 2 or clinical endpoints. Mapping/matching/history remain labelled previews.

## M3 — Source connector and two demo databases (connection/introspection implemented)
User-confirmed sequence (ADR-017): close out M2, complete the documented upstream
research/compatibility gate, reproduce both pinned source environments, then implement
generic vendor connectors for authenticated database connection and health checks.
The gate records exact EHR/database versions and image digests, startup, credentials,
schema characteristics, direct DB suitability, resource budgets, seed/reset procedures,
licenses and connector requirements. No floating tags. OpenMRS/OpenEMR are demo
integrations, never special cases in core connector code.
Acceptance for this slice: independent fictional source databases initialized from
their pinned EHR installers; read-only connector identities; successful authenticated
connection and health checks for both; bad credentials/unreachable/wrong-database
failures redacted and tested; reproducible reset and startup; no source secrets centrally.
Schema introspection begins only after both environments and connection contracts are
reproducible and tested. ADR-019 now adds metadata-only base-table introspection and
the immutable local scan registry, tested against both accepted sources. Capture
declared keys only; enforce allowlists/count/byte/deadline bounds. ADR-020 now adds
bounded clinical profiling and relationship evidence as pre-M5 prerequisites.
Extraction/cursors and runtime drift remain later M3 slices. Full M3 is not claimed complete.
Compatibility/deployment evidence is in `docs/research/M3_COMPATIBILITY_GATE.md`;
startup/reset and local health commands are in `infra/demo/README.md`.

## M4 — FHIR catalog and mapping proposal contracts (implemented, ADR-019)
Verify/cache `hl7.fhir.r4.core#4.0.1` and its checksum/dependencies (ADR-018;
BD-Core is outside demo scope); normalized FK
graph, table domain classification, bounded candidate retrieval; provider abstraction
and validated task output with local adapter. Acceptance: bounded prompts, no secrets
or arbitrary SQL, invalid JSON/candidate/path/AST rejected, ambiguous fields retained.
Evaluate model accuracy/hardware; do not auto-approve mappings.

Observed: official core archive verified/cached with manifest/checksum lock; normalized
declared FK graph and lexical table classification; datatype/choice-aware bounded
retrieval; typed tasks/AST output checks; runtime/model-pinned Ollama adapter; bounded
correction and retained unresolved fields. Local SQLite stores immutable scan/task/
proposal evidence with exact-input reuse, without M5 approval/release commands.
The local evaluation uses a small synthetic metadata benchmark, not clinical records.
Run and acceptance details: [M4 runbook](M4_RUNBOOK.md), [verification](VERIFICATION.md).

## M5 — Hospital registry and review

ADR-020 confirms bounded clinical evidence before review: reproducible fictional
seeds for both pinned sources, local profiling and complete/incomplete deterministic
relationship checks with immutable observations/access audit. This first prerequisite
slice does not implement approval or extraction cursors. Patient review/releases come
first, then encounters/observations and all discovered clinical domains; every source
column stays in the coverage inventory. Human investigation can supply more evidence;
judgment alone cannot bypass relationship checks. Commands/review files precede M8 UI.
See [evidence runbook](EVIDENCE_RUNBOOK.md).

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
