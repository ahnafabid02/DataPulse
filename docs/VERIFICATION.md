# DataPulse verification

Verified 2026-10-07 in X:\DataPulse. M1, M1-UI and M2 are implemented; later
milestones remain planned. No patient data or real hospital infrastructure was used.
The repository is on `main` with the user-authorized GitHub remote. Earlier results
below are historical; the latest M2 checks are listed first.

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

BD-Core 0.4.6 is a research-backed candidate, not a fetched/checksum-verified package
or compliance claim. National identifier namespaces and verified-identifier evidence
need integration-owner review. OpenMRS/OpenEMR images/database compatibility and
controlled seed procedures must be pinned/verified at M3. Extraction snapshot/revision
ordering, safe transformation grammar and terminology availability remain milestone
deliverables. Production access, audit, retention and governance are not implemented.
Local database role is a bootstrap superuser; production roles must be separated.

## Next milestone

Implement **M2: source onboarding and access control** only: organization/source
registration/read APIs, authenticated source principal binding and admin/source
scopes, rotating token handling, append-only audit, migrations and authorization/
cross-source denial/API tests. Do not implement LLM mapping or identity yet.

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
