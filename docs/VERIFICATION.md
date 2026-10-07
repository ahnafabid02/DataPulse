# Phase 0 and M1 verification

Verified 2026-10-07 in X:\DataPulse. The architecture/design covers later milestones;
M1 and the user-requested M1-UI preview are implemented. No patient data was imported. Git initialized on `main`,
with files uncommitted and no remote configured.

## Observed checks

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
