# Development and verification

Python target is 3.12 (matching Docker and CI). Runtime pins are in requirements.txt,
dev pins in requirements-dev.txt; install the package with `--no-deps -e .` after
installing pins. Refresh dependencies deliberately and rerun checks. Python 3.14
is not the target even if it is the host default.

Copy `.env.example` to `.env`, set a development-only database password and matching
DATAPULSE_DATABASE_URL (URL-encode reserved password characters). Compose overrides
the host DB URI with service hostname `db`. Password-free examples intentionally
fail until configured. Do not print rendered Compose environments with secrets.

Native commands are in README. All Docker components use local-only host ports.
`docker compose up --build` waits for DB health, runs migration in a one-shot service,
then starts API as a non-root user. Persisted DB volume survives ordinary stop/down;
do not delete volumes unless intentionally resetting controlled demo data.

## Checks

Unit tests use temporary SQLite files or isolated mocks. They cover configuration,
health/error redaction, normalized schema invariants/fingerprint, migration lifecycle
and SQL constraints. SQLite is not a supported central deployment database.

For real PostgreSQL checks, create a dedicated empty **disposable** database and set:

```powershell
$env:DATAPULSE_TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DISPOSABLE_DB'
.venv\Scripts\python.exe -m pytest -m postgres
```

These tests migrate up/down and modify foundation tables; never point them at real
data or the normal development database. Tests refuse a nonempty database. CI
provides its own fresh database and runs all tests including PostgreSQL markers.
Default local tests skip this check when the variable is unset and report the skip.

`ruff check .`, `ruff format --check .`, `mypy src`, and `pytest` are required.
`docker compose config --quiet` validates structure using a configured .env without
printing secrets, but a configured .env is required for actual startup. Image build
and running health probes require a working Docker daemon. The verification record
lists observed results and environment limitations; do not claim CI ran locally.

## Review checklist

Scope includes M3 scans, M4 proposals and ADR-020 bounded clinical evidence; clinical,
approval and agent HTTP routes are absent. Hospital operations are local commands,
with separately provisioned Alembic SQLite storage. ORM and central Alembic definitions
match. Readiness checks revision, not connectivity alone. Source credentials never
enter central model. Schema structural hashes ignore sample/time noise. Patient data
or DB errors never enter operational logs. Connector contracts contain no raw SQL.
Cross-source linkage/provenance decisions align across domain, flow and agent docs.

## Early interface (M1-UI)

`web/` requires Node 24 and uses its checked-in npm lockfile. Run `npm ci`, `npm test`,
`npm run build`; generated static assets are ignored and packaged by the Docker
frontend build stage. Native backend startup requires this build first to serve `/`.
Static UI routes are excluded from OpenAPI; authenticated M2 APIs are included.
The optional Vite server proxies health and `/v1`; configure the backend browser
origin to its port 5173 for mutations. Hospital setup persists in PostgreSQL.
Review/matching/history previews remain in memory and contain fictional data.
See README for hidden-entry administrator bootstrap/recovery and `UI_DESIGN.md`
for integration boundaries. Passwords must never be CLI arguments or test output.

## M3 source checks

Follow `infra/demo/README.md` for the pinned research/startup gate and standalone
source health commands. Real connector integration requires only the two verified
empty or exactly recognized seeded fictional fixtures. Set `DATAPULSE_DEMO_TEST_DIR` to the generated
`.tmp/m3-demo` directory, then run `pytest -m source_db --tb=no`.
Tests refuse other hosts/ports/source UUIDs or unrecognized clinical baselines and
exercise zero-row denied DML, temporary DDL, other-database denial and connection/
credential/TLS failures. Evidence tests read bounded fictional column values; no test
alters clinical records. Without this opt-in, six source integration cases are skipped in normal
CI/local checks. Unit coverage still tests connection contracts, credential binding,
transport policy, redaction and cleanup. The real pinned EHR runs are local deployment
evidence; hosted CI for this uncommitted change is not claimed.

Run `infra/demo/seed_clinical.py` after source startup/provision before evidence tests.
The dedicated seed operator owns fictional writes, guarded by version/ownership
checks; connectors remain SELECT-only. Current local registry revision is
`hospital_0003`. Read [evidence runbook](EVIDENCE_RUNBOOK.md) before profiling.

## M4 checks

Follow [M4 workflow](M4_RUNBOOK.md). Default tests use synthetic definitions, explicit
temporary registry migrations and a loopback fake provider server, with no package
download or local model requirement. They verify forged candidates/paths/source IDs,
invalid types/ASTs/terminology, uncertain fields, retries, persistence/immutability,
proposal reuse, runtime/model pins, redirects/cloud forwarding, size limits and total
HTTP deadlines including slow-drip responses. Source opt-in additionally scans both
actual DBs twice, saves/reopens registries and tests metadata limit cleanup.

The official package cache and digest-pinned local model evaluation are explicit
runbook commands, separately recorded in VERIFICATION.md. Synthetic benchmark
results are not clinical accuracy or calibrated confidence. The hospital migrations
are packaged with the Python module; they must work in a built wheel, not only an
editable checkout. Central schema/API contracts remain M2.
