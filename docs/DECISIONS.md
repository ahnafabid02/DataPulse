# Architecture decisions

Date: 2026-10-07. Accepted unless explicitly labelled deferred. Major changes require
a superseding ADR and updates to affected contracts, tests and rollout plans.

## ADR-001 — Canonical interoperability target
Decision: FHIR R4 4.0.1. Context: broad interoperability and the BD-Core base.
Consequence: nested typed resources/profile validation; no generic full FHIR server
implementation. R4B/R5 need explicit migration, not library defaults.

## ADR-002 — Bangladesh compatibility
Decision: BD-Core where applicable, evaluate package 0.4.6 before M4.
Context: DGHS publishes an informative evolving guide.
Consequence: pin verified packages/profiles and retain package versions; no claim
of current BD-Core conformance. Review national identifier namespace semantics.

## ADR-003 — Source-specific mapping registry
Decision: mappings scoped to source deployment/database/scan and immutable versions.
Context: equal vendor/product names do not imply equal schemas.
Consequence: no universal field mapping keyed merely by DB engine.

## ADR-004 — Patient records in model context
Decision: permitted when useful for mapping or difficult identity reasoning.
Context: semantics can require rich real records.
Consequence: bounded application-mediated access, audit and deployment controls;
no model-held DB secrets or arbitrary SQL, no artificial design-wide anonymization.

## ADR-005 — Deterministic approved runtime
Decision: reviewed releases interpreted by versioned safe transformations; no model
in normal synchronization. Consequence: drift/unknowns pause affected recipes and
re-enter review rather than improvising output.

## ADR-006 — Agent deployment boundaries
Decision: Agent 1 hospital-side per source; Agent 2 central. Context: schema/secrets
belong near source, global identity belongs centrally. Consequence: separate modules
and deployments, no giant agent service and no central source secret registry.

## ADR-007 — Identity preservation and linking
Decision: keep original source patient IDs, maintain reversible global identity links.
Context: false-positive association is worse than duplicate records.
Consequence: one active link/source patient, reviewed conflict/relink, immutable history.
Initially all cross-source candidate links require human approval; model-only/fuzzy
auto-linking is prohibited.

## ADR-008 — Clinical source/provenance preservation
Decision: immutable source resource versions and provenance with release/interpreter
versions. Consequence: longitudinal query assembles history; no destructive collapse
or silent preference for one hospital's demographics.

## ADR-009 — Replaceable models
Decision: provider ports with constrained JSON and validated output; local quantized
HTTP inference supported, remote/server providers optional. Consequence: no model
SDK in domain logic; M1 installs no model or agent framework.

## ADR-010 — Demo EHRs are integrations
Decision: OpenMRS/OpenEMR are independent demo sources, not architecture constants.
Context: future databases vary. Consequence: generic normalized schema/connector
ports. Exact EHR image versions/database compatibility are deferred to M3, verified
against upstream pinned compose/release commits, never selected from `latest`.

## ADR-011 — Initial stack and topology
Decision: Python 3.12/FastAPI/Pydantic 2/SQLAlchemy 2/Alembic/psycopg 3, PostgreSQL 16,
Docker Compose; synchronous DB handlers, modular central app, future worker process.
Context: mature REST/ML tooling; small local footprint. Consequence: no Kubernetes,
broker, vector DB or microservice fleet until a measured need. React UI timing is
superseded by ADR-015 at the user's explicit request.

## ADR-012 — FHIR persistence and validation
Decision: constrained JSONB source repository behind a port, official HL7 validation
adapter later. HAPI JPA is evaluated as an alternative when standard FHIR operations
are required. Context: avoid full FHIR reimplementation and extra JVM service during
foundation. Consequence: custom API makes no general FHIR REST conformance claim;
external storage would require reconciled outbox, not cross-store atomic assumptions.

## ADR-013 — Hospital state and durable processing
Decision: single-process SQLite hospital registry/outbox for first demo, PostgreSQL
jobs/outbox centrally. Context: minimal services and auditable retries.
Consequence: concurrency/durability tests before sync; hospital multiwriter requires
PostgreSQL migration. M1 SQLite tests are not central runtime support.

## ADR-014 — Foundation scope
Decision: M1 implements health/config/logging, organization/source migration and
normalized schema/connector interfaces only. Context: user explicitly requests Phase
0 then one coherent foundational milestone. Consequence: no mapping/identity/ingestion
implementation, no dummy business endpoints, no demo EHR containers until M3.

## ADR-015 — Early friendly interface (supersedes UI timing in ADR-011/014)
Decision: add M1-UI before M2 at the user's request. English React/TypeScript UI
built with Vite, served as static assets from the central app at `/`. Hash navigation
keeps direct links simple; no additional runtime service or separate hosting.
Context: non-technical users need a self-explanatory workspace before backend expansion.
Consequence: live health status plus clearly labelled, fictional, session-only hospital,
field-review, identity-review and patient-history workflows. No business writes,
credentials or real patient data. No browser persistence. Unconfirmed sample identities
stay separate even in the preview. Authenticated integration remains M2 and later.
Styles use a shared responsive design system, plain language, native accessible
dialog/form controls, reduced-motion support and keyboard focus management.

## ADR-016 — Authenticated local onboarding (supersedes hospital-preview boundary in ADR-015)

Accepted M2 at the user's explicit request. The authoritative decision is
[authenticated onboarding](adr/0016-authenticated-onboarding.md): persistent
hospital setup UI, separate administrator/connector principals, revocable hashed
credentials, extensible role grants, logical retirement and transactional audit.
Only hospital setup moves beyond previews; M3–M9 capabilities remain deferred.
