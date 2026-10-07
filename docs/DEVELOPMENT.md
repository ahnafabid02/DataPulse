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

Scope matches M2; future clinical/agent/connector routes are not present. ORM and Alembic definitions
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
