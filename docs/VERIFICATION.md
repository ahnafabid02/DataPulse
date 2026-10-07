# DataPulse verification

Verified 2026-10-08 in X:\DataPulse. M1–M4 and ADR-020 bounded clinical evidence
are implemented; extraction cursors and M5 review/releases onward remain planned.
Only generated fictional clinical rows were used; no real patient data or hospital
infrastructure was used.
The repository is on `main` with the user-authorized GitHub remote. Earlier results
below are historical; the latest evidence checks are listed first.

## ADR-020 evidence prerequisite checks (2026-10-08)

- Final full backend suite: **164 passed**, with a fresh disposable central
  PostgreSQL database and all six real-source integration cases; no skips. Ruff lint
  and format (157 files), strict mypy (35 source files), dependency consistency and
  whitespace checks pass. One existing Starlette/httpx deprecation warning remains.
  Frontend is unchanged. Hosted CI has not run; changes remain uncommitted.
- Both exact pinned EHRs were seeded with three fictional patients, similar names/
  identifiers, missing demographics and repeated visits. OpenMRS has four encounters
  and four typed observations. OpenEMR has five encounters (one labelled orphan),
  four vitals and nine companion forms; row IDs differ from clinical patient/encounter
  keys. DataPulse readers retain SELECT-only grants and pass real DML denials.
- Seed repeats verify fixed columns/counts plus complete owned-row integrity receipts
  without new writes. Version drift, missing receipts, foreign configuration/rows and
  reserved-key collisions refuse adoption. Per-source transactions and explicit
  source reset remain separate from central state and local evidence.
- Clean-volume reset/reinstall/provision/reseed reproduced both structural fingerprints
  and **all owned fixture row hashes**. Initial comparison caught three auto-generated
  OpenEMR timestamps; the final seed explicitly pins them. Final comparison reports
  `structural_fingerprints_equal:true`, `full_seed_row_digests_equal:true` and
  `both_seeds_verified:true`. Reproducibility tooling and refusal/mismatch tests are
  checked in; source installer-generated metadata is not claimed byte-identical.
- One reset exposed the pinned OpenMRS EMR API unknown-provider/property inconsistency.
  Source research identified the startup lookup and existing public sentinel UUID;
  guarded property recovery restored authenticated REST readiness. The launcher
  implements this conditional recovery, with idempotence/foreign-value/restart tests.
  Subsequent reset reached readiness and reproduced the final seed. No provider or
  constraint was deleted; optional module warnings do not establish full O3 acceptance.
- Real bounded profiles retain source value types/null counts. OpenMRS encounter ->
  patient evidence: four source rows, three target rows, one repeated source-key group,
  zero duplicate target groups and zero unmatched rows; `needs_review`, never approved.
  OpenEMR pid -> pid detects its one orphan; pid -> row id detects five unmatched rows;
  name -> name detects a duplicate target-key group. Limits return `incomplete` with
  population metrics absent, rather than claiming sample-based proof.
- Snapshot engine restrictions, composite/null-key semantics, wrong source/fields,
  before/after structural drift, scalar/serialized bounds, literal identifier quoting,
  redacted failures and audit-before-read are tested. Hospital Alembic `hospital_0003`
  adds immutable access/evidence tables; migration preservation/downgrade and saved
  observation reopen/integrity checks pass. Central revision stays `0002_access`.
- Fresh schemas, evidence requests/results and coverage inventories are prepared in
  ignored `data/hospital/openmrs*` and `openemr*` paths. Inventories preserve all
  **3,089 OpenMRS + 3,782 OpenEMR columns** as awaiting human coverage review; no
  automatic clinical exclusions. M4 proposal commands remain metadata-only.
- Final wheel build succeeds; isolated installed package provisioning of the new
  hospital migration was verified. Full M5 edit/approval/assemblies/releases,
  authenticated review, model relationship proposals, clinical extraction/ingestion
  and complete FHIR instance validation are not claimed by this first slice.

Commands and limits: [evidence runbook](EVIDENCE_RUNBOOK.md).
Primary-source/seed/startup findings: [research gate](research/M5_FICTIONAL_SEED_GATE.md).

## M4 observed checks

- Final backend suite: **136 passed**, including a newly created disposable central
  PostgreSQL database and both accepted EHR databases; no tests skipped. Ruff lint
  and format (145 files), strict mypy (31 source files), dependency consistency and
  whitespace checks pass. One existing Starlette/httpx deprecation warning remains.
  Frontend code is unchanged from the earlier 7-test M2 verification.
- Final wheel was built and installed into an isolated test environment. Imports
  came from the installed wheel; packaged hospital migrations provisioned a fresh
  registry and packaged catalog code verified the official cached FHIR archive.
- Official `hl7.fhir.r4.core#4.0.1` archive was downloaded from HL7, verified at
  4,531,911 bytes and SHA-256
  `b090bf929e1f665cf2c91583720849695bc38d2892a7c5037c56cb00817fb091`.
  Its manifest declares version 4.0.1, no dependencies and CC0-1.0. Checksums are
  locally measured artifact pins, not an asserted HL7-published signature.
  Cached package load, manifest checks, nested datatype expansion, actual choice
  element names and required terminology metadata were exercised locally.
- SELECT-only metadata scans observed OpenMRS: 239 base tables, 3,089 columns,
  230 tables with declared primary keys and 903 declared foreign keys; OpenEMR:
  283 base tables, 3,782 columns, 238 tables with declared primary keys and no
  declared foreign keys. Missing OpenEMR links are not inferred from names.
  MariaDB hides TABLE_CONSTRAINTS from SELECT-only users; verified upstream source
  led to reading KEY_COLUMN_USAGE directly without expanding reader permissions.
- Both sources passed repeated unchanged scan fingerprints, explicit local Alembic
  registry provisioning, save/reopen persistence, wrong-source guards and metadata
  limit cleanup. Immutable scan/run triggers, structural deduplication, preserved
  per-scan comments/defaults and migration upgrade/downgrade are tested.
- Actual source-bound local model runs produced OpenMRS `person.birthdate` ->
  `Patient.birthDate`, retaining gender as unresolved for missing source-value/code
  evidence. OpenEMR `patient_data.DOB` -> `Patient.birthDate` and
  `patient_data.fname` -> `Patient.name[].given[]` were saved as unapproved proposals.
  Repeating compatible commands reused each saved run without new inference.
  Separate prepared registries, scan receipts, schemas, selected fields and proposal
  JSON files are saved under ignored `data/hospital/openmrs*` and `openemr*` paths.
  Both prepared registries were checked again with `reused:true`.
- Final six-case synthetic metadata evaluation: **6/6 expected dispositions**;
  each includes unknown-field retention and an untrusted identifier text case.
  Measured case times: 8.422, 18.141, 17.750, 8.500, 0.000 and 8.625 seconds.
  This tiny fixed benchmark is not calibrated confidence, a clinical accuracy
  estimate or evidence of complete EHR mapping. Earlier broader grammar attempts
  produced invalid output; narrowing host-owned per-task grammars was necessary.
- Local model: existing `qwen2.5-coder:3b`, Q4_K_M, artifact bytes 1,929,912,626,
  digest `f72c60cabf6237b07f6e632b2c48d533cef25eda2efbd34bed21c5e9c01e6225`;
  observed Ollama runtime 0.33.2, context 16,384, temperature 0, seed 7.
  Host: AMD Ryzen 7 5800H, 8 cores/16 logical CPUs, 17,024,741,376 bytes RAM,
  NVIDIA GeForce RTX 3060 Laptop GPU. `/api/ps` sampling during actual source runs
  observed up to 2,721,946,009 model bytes, all reported in VRAM; this is sampled
  model allocation, not a process/system peak or hardware minimum. No new model
  install was needed. Source-run timings in that observation were about 30-35 s.
- Host checks reject malformed JSON, candidate/path/source/evidence forgery,
  unsupported or oversized ASTs, incompatible types, unsupported reference targets,
  unverified required codes, grouping errors and model calibration claims. Input
  partitions never contain a full DB schema; every selected field is proposed or
  unresolved. The adapter rejects changed model/runtime pins, cloud forwarding,
  redirects, oversized responses and slow-drip deadline overruns. Corrections are
  bounded to two after the initial attempt. No raw model output is operationally logged.
- No clinical rows were sampled/extracted, no mapping was approved, and no central
  migration or HTTP/UI workflow was added. M5 assemblies/approval/releases and M6
  deterministic transformation/full FHIR instance validation remain future work.
  Local SQLite file owners remain trusted; production retention/encryption/durability
  and remote model/TLS deployment acceptance are not claimed. Changes are uncommitted;
  hosted CI for M4 has not run.

Commands: [M4 runbook](M4_RUNBOOK.md). External evidence:
[M4 research gate](research/M4_FHIR_PROVIDER_GATE.md). ADR-019 records scope.

## M3 connection slice observed checks

- Final backend suite: **88 passed**, including dedicated disposable central
  PostgreSQL and both actual pinned EHR source databases; no skipped tests. Ruff
  lint/format, strict mypy (17 source modules), dependency consistency, Compose
  validation and whitespace checks pass. The unchanged frontend passed 7 tests,
  strict TypeScript and production build during M2 closeout in this session.
- M2 was closed out with 49 backend tests including PostgreSQL, 7 frontend tests,
  lint/format/type/build checks and successful hosted CI for the existing M2 commit.
- Primary-source research covers all requested EHR versions, database compatibility,
  digest-pinned images, credentials, schema characteristics, direct DB suitability,
  resources, seeds/resets, licensing and connector requirements. The research gate
  and two clean source installations passed before connector code began.
- OpenMRS Reference Application 3.7.1/core 2.8.8 on MariaDB 10.11.7 and OpenEMR
  8.4.1/schema 543 on MariaDB 12.3.3 initialized using their original installers.
  Exact image digests, installed metadata and zero-patient baselines were verified.
  Two independent clean resets reproduced the accepted baseline; ordinary restart
  preserved versions and source configuration. The central application stayed ready.
- The OpenMRS schema-health seed disables random patients and optional rich
  metadata/terminology loading using supported upstream settings. It retains actual
  core/module migrations. Its first install needs a post-install servlet restart;
  the launcher bounds acceptance at 15 minutes. Optional address-hierarchy/XML
  warnings remain; full O3 clinical metadata/functionality is not accepted.
- A generic vendor adapter authenticated to both source DBs with separate source-bound
  SELECT-only credentials and reported healthy. Real source tests reject INSERT,
  UPDATE, DELETE, temporary-table creation and reads from another database. Tests
  also cover wrong passwords/database/vendor, unreachable port and rejected TLS.
  Zero-row DML attempts cannot alter clinical records even if permissions regress.
  Final standalone health commands both returned healthy (16 ms each in that sample).
- MariaDB 10.11.7 lacks advertised TLS in this demo; the adapter rejects before
  authentication rather than falling back. MariaDB 12.3.3's untrusted certificate
  is rejected with the correct TLS category even when PyMySQL wraps the exception.
  Verified remote TLS success remains environment-dependent and untested.
- Unit checks cover inline-secret/raw-SQL rejection, timeout/TLS bounds, credential
  file limits/rotation, exact source binding, restricted grants, error redaction,
  connection/cursor cleanup, health invariants and safe CLI failures. A regression
  check prevents normal context refresh from triggering a first-install restart.
  A separate regression bounds TLS negotiation before authentication; the pinned
  driver otherwise clears its TCP timeout before the TLS handshake.
- Resource observations and the conservative local budget are recorded in the
  compatibility gate; sampled memory is not a peak/minimum capacity certification.
  M3 local secrets remain in ignored files and source volumes. No central migration,
  API connectivity endpoint, introspection, mapping, Agent 1 or clinical API was added.
- Hosted CI success above belongs to M2 commit `92816c2`; these M3 changes have not
  been committed/pushed and no hosted M3 CI success is claimed. Existing test-client
  deprecation warnings remain outside this scope.

## M2 observed checks

- Final backend suite: **49 passed**, including PostgreSQL; no skipped tests.
  Covers administrator bootstrap/recovery, password hashing/change, login lockout,
  session expiry/revocation, wrong-origin/header rejection, bounded requests,
  validation/log secret redaction, cross-source and cross-role denial, credential
  transport isolation, atomic onboarding, duplicate codes, revisions, suspension,
  rotation/revocation, retirement, pagination and registration reload/restart.
- Real PostgreSQL test exercises registration CRUD, connector scope, token rotation,
  readiness, ORM/migration comparison, and direct audit UPDATE/DELETE/TRUNCATE denial.
  Upgrade/downgrade pass against a dedicated empty disposable database. Tests leave
  that database empty. SQLite additionally verifies upgrade preservation of existing
  M1 registration data and rollback of a business write when its audit insert fails.
- Frontend: **7 passed**, including signed-out setup, authenticated atomic save,
  one-time credential display/removal, reloaded registrations and conflict messages.
  Existing ambiguous-date and conservative sample matching tests still pass.
- Ruff lint and formatting, strict mypy (14 source files), TypeScript and production
  frontend build pass. `pip check` reports no broken requirements.
- Docker frontend/Python build and Compose deployment succeeded; migration
  `0002_access` applied without dropping normal demo data. Local API and PostgreSQL
  health checks passed. No administrator password was invented for the user; the
  hidden-entry operator bootstrap in README remains their first-use setup step.
- Browser verification used an isolated temporary SQLite-backed fixture on port
  8001, not the user's demo database: sign-in, two-step setup, one-time key display,
  dismiss/reload persistence, source suspension and corresponding audit record.
  Desktop and 390px mobile layouts checked; mobile dialog fits and no horizontal
  overflow. Mobile navigation opens correctly; browser reported no console errors.
  The normal packaged workspace is served on port 8000 with PostgreSQL.
- No hospital DB access, schema extraction, Agent 1/Agent 2, clinical ingestion or
  patient APIs were introduced. Preview decisions remain fictional and session-only.
- A final expanded PostgreSQL fixture initially assumed the database contained
  only the lifecycle source, though earlier checks deliberately created two other
  sources. The assertion now checks retirement of the specific target. The verified
  disposable fixtures were cleared and the complete final suite passed.
- Local checks do not assert hosted GitHub Actions success. The existing test-client
  dependency emits a deprecation warning; it does not affect test results.

## Historical M1 observed checks

- Python 3.12.10 native virtual environment installed successfully. Dependencies
  pinned in runtime/dev requirements; clean editable install with no build isolation
  passed. `pip check`: no broken requirements.
- `pytest`: **31 passed**, including the PostgreSQL test; no skipped tests in the
  final full run. Unit coverage includes secrets redaction/config failure, health
  revision/connection failures, request metadata, schema validity/order-independent
  fingerprint, external FK preservation, bounded connector payloads.
- SQLite and PostgreSQL migration tests: upgrade, metadata comparison, per-hospital
  source uniqueness, vendor/status/nonblank checks, FK enforcement, delete restriction,
  downgrade and readiness behavior passed. PostgreSQL ran against a separate empty
  `datapulse_test` database; its application tables were removed by the test. Normal
  `datapulse` development database retains the foundation migration.
- Ruff lint and formatting checks passed; strict mypy passed for 11 source files.
- Docker Compose configuration validation passed. Clean Docker image build passed
  using Python 3.12.14 and the pinned runtime dependency set on Linux.
- PostgreSQL 16.14 container healthy. One-shot migration service exited 0.
  API container healthy, runtime UID 10001 (non-root).
- Real API probes: `/health/live` -> `{"status":"ok"}`;
  `/health/ready` -> `{"status":"ready"}`. OpenAPI contains exactly those two paths.
- Required documentation presence and relative links checked; local environment,
  virtual environment and temporary files confirmed ignored by Git.
- CI workflow created with a PostgreSQL service; the hosted CI job has not been run.

Initial sandbox restrictions blocked dependency downloads, Docker access and the
Windows asynchronous event loop's loopback sockets. Authorized elevated checks
resolved those environment limitations; application behavior was not changed to
work around a failing test. Docker's credential helper directory was added only to
the command's PATH, not machine settings.

One upstream development-only warning remains: Starlette 1.7.0 deprecates its httpx
test client integration in favor of httpx2. Current pinned integration passes; migrate
the test dependency deliberately in a later tooling update. Alembic configuration's
path separator warning was fixed.

## Internal consistency review

- Hospital registry authority and central mapping metadata are distinct everywhere.
- M1 normalized schema/profile/extraction contracts match documented connector ports.
- Mapping/model output cannot approve mappings; runtime consumes reviewed versions.
- Source records and identity links remain separate; no destructive merge appears
  in schema or design. Initial cross-source linking policy is human-reviewed.
- Full FHIR/profile validation and JSONB clinical storage remain planned M6 behavior;
  no M1 endpoint asserts FHIR/BD-Core conformance.
- Credentials are excluded from central source metadata and shared schema contracts.
- M1 health endpoints intentionally have no auth; M2 gates all business endpoints.

## Assumptions and unresolved risks

Initial hospital registry assumes one writer/deployment. Central services remain
modules before scale justifies separate services. A controlled Patient/Encounter/
Observation demo slice precedes broader clinical domains. Local model selection and
hardware limits are evaluated at M4. No real hospital schemas were available in M1.

ADR-018 selects `hl7.fhir.r4.core#4.0.1`; M4 now verifies its package/manifest and
records the empty dependency set. BD-Core is outside demo scope.
Verified-identifier evidence needs integration-owner review.
OpenMRS/OpenEMR images/database compatibility and
controlled seed procedures must be pinned/verified at M3. Extraction snapshot/revision
ordering, safe transformation grammar and terminology availability remain milestone
deliverables. Production access, audit, retention and governance are not implemented.
Local database role is a bootstrap superuser; production roles must be separated.

## Next milestone

Current next milestone: M5 hospital review, assemblies and immutable approved
mapping releases. Clinical profiling/extraction and remaining M3 cursor/drift work
still need separate acceptance before a real record-to-FHIR runtime. Earlier M2/M3
closeout entries below are historical.

M2 closeout on 2026-10-07: 49 backend tests passed against a newly created disposable
PostgreSQL database; 7 frontend tests, Ruff lint/format, strict mypy, TypeScript and
production frontend build passed. The existing packaged application's readiness
probe returned ready. Existing commit `92816c2405e925de0840d9f84b21884d3a7c0c80`
has a successful [hosted CI run](https://github.com/ahnafabid02/DataPulse/actions/runs/37631400414).
Earlier statements that hosted CI was unverified are historical. The operator's
personal first-use administrator bootstrap remains manual; tests verify its behavior,
not the operator's choice of credentials. No existing credentials were changed.

The user authorized the **M3 compatibility gate then connection/health slice**.
See the roadmap and ADR-017. Introspection follows successful reproducibility and
connection-contract testing; mapping/identity/clinical implementation remains deferred.

## M1-UI verification (2026-10-07)

- English React/TypeScript interface built and served by the local API at port 8000.
  Six screens cover overview, hospitals, field review, patient matching, patient
  records, and help. All business records/actions are fictional and session-only.
- Final backend run: **33 passed**, including the PostgreSQL lifecycle test.
  Ruff lint/formatting and strict mypy passed. The test database was recreated
  after an initial failure reported that it no longer existed; final run has no skips.
- Frontend: **5 tests passed**, including unavailable health, ambiguous-date
  approval blocking, source separation, explicit identity confirmation, reset,
  and the fictional hospital wizard. Strict TypeScript and production build passed.
- Dependency installation audit reported zero vulnerabilities. Docker rebuilt the
  interface and API successfully; migration completed and live readiness responded.
- Browser checked the built app at 1280px desktop and 390px mobile: hospital wizard,
  field correction, separate source history, confirmed combined history, hospital
  filter, reset, and live status refresh. Mobile document width stayed within the
  viewport. Menu focus/Escape restored focus correctly; no browser console errors.
- A local development password appeared in the failing database test traceback.
  It was replaced in PostgreSQL and the ignored local environment file, and the
  preview services were recreated. Use short tracebacks for future database checks.
- Screenshot inspected in browser; saving its image through the browser tool was
  denied by its filesystem restrictions. Hosted CI has not been run.

See `docs/UI_DESIGN.md` for vocabulary, preview boundaries, and future integration.

## Created file inventory

Root/tooling:
`AGENTS.md`, `README.md`, `pyproject.toml`, `requirements.txt`,
`requirements-dev.txt`, `.gitignore`, `.dockerignore`, `.env.example`,
`compose.yaml`, `Dockerfile`, `alembic.ini`, `.github/workflows/checks.yml`.

Documentation:
`docs/ARCHITECTURE.md`, `docs/DOMAIN_MODEL.md`, `docs/DATA_FLOW.md`,
`docs/DATABASE_DESIGN.md`, `docs/API_CONTRACTS.md`, `docs/AGENT_1_MAPPING.md`,
`docs/AGENT_2_IDENTITY.md`, `docs/FHIR_STRATEGY.md`, `docs/SECURITY.md`,
`docs/DECISIONS.md`, `docs/IMPLEMENTATION_ROADMAP.md`, `docs/DEVELOPMENT.md`,
`docs/VERIFICATION.md`, `infra/demo/README.md`.

Package:
`src/datapulse/__init__.py`, `src/datapulse/central/__init__.py`,
`src/datapulse/central/app.py`, `src/datapulse/central/config.py`,
`src/datapulse/central/db.py`, `src/datapulse/central/models.py`,
`src/datapulse/central/logging.py`, `src/datapulse/contracts/__init__.py`,
`src/datapulse/contracts/schema.py`, `src/datapulse/connectors/__init__.py`,
`src/datapulse/connectors/base.py`.

Migrations:
`migrations/env.py`, `migrations/script.py.mako`,
`migrations/versions/0001_foundation.py`.

Tests:
`tests/conftest.py`, `tests/test_config.py`, `tests/test_health.py`,
`tests/test_schema.py`, `tests/test_connector_contract.py`,
`tests/test_migrations.py`, `tests/test_postgres.py`.

Ignored local setup: `.venv/`, `.tmp/`, generated package metadata and caches,
`.env` with a random development-only password. These are not deliverable source files.
