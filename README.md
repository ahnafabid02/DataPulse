# DataPulse

Healthcare interoperability platform for heterogeneous hospital databases, targeting
FHIR R4 with Bangladesh Core compatibility where applicable.

## Status

Phase 0, M1, M1-UI and M2 are complete in this revision. M1 provides a
central API shell, validated configuration, health checks, structured request logs,
organization/source database models and migrations, normalized schema contracts,
and a connector protocol. No mapping agent, identity matcher, clinical ingestion,
or FHIR server is implemented yet. The requested early English interface is now
available as M1-UI, with live status checks and clearly labelled sample workflows.
M2 adds administrator sign-in, saved fictional hospital/source setup, separate
connector identities, key rotation/revocation and append-only activity records.
This is a local demo, not a production deployment.

## Architecture and documentation

Start with [architecture](docs/ARCHITECTURE.md), [decisions](docs/DECISIONS.md), and
[roadmap](docs/IMPLEMENTATION_ROADMAP.md). The documents define future contracts;
only endpoints explicitly marked implemented M1/M2 exist today.

- [Domain model](docs/DOMAIN_MODEL.md)
- [Data flow](docs/DATA_FLOW.md)
- [Database design](docs/DATABASE_DESIGN.md)
- [API contracts](docs/API_CONTRACTS.md)
- [Agent 1 mapping](docs/AGENT_1_MAPPING.md)
- [Agent 2 identity](docs/AGENT_2_IDENTITY.md)
- [FHIR strategy](docs/FHIR_STRATEGY.md)
- [Security](docs/SECURITY.md)
- [Development and verification](docs/DEVELOPMENT.md)
- [Verified results and complete file inventory](docs/VERIFICATION.md)
- [User interface design and preview boundaries](docs/UI_DESIGN.md)

## Local setup

Requirements: Python 3.12, Docker Desktop with Linux containers for PostgreSQL.
From PowerShell in the project root:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pip install --no-deps -e .
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Replace both local database password occurrences in .env with the same value.
docker compose up -d db
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn datapulse.central.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Alternatively, `docker compose up --build` runs database, one-shot migrations, and
the API. It requires a configured `.env`; there are no built-in passwords.
The database role is a local development bootstrap superuser, not a production role.

This working directory already has an ignored `.env` with a generated random local
password and the verified containers running. Fresh checkouts need the setup above.

Create your administrator after migrations. Enter your chosen username/password
at the prompts; the password is hidden and is never stored as plaintext:

```powershell
# Docker setup (interactive terminal):
docker compose exec -it api python -m datapulse.central.admin
# Or native setup:
.venv\Scripts\python.exe -m datapulse.central.admin
```

There is no default administrator password or public signup. Only one administrator
can be bootstrapped. For local recovery, run the same command with `--reset` and the
existing username; this revokes all sessions and records an operator audit event.

Open **http://127.0.0.1:8000/#hospitals** and sign in. Save only fictional hospitals
and source systems; setup persists across reload/restart. Save the source access key
securely when it is shown once. It authenticates a connector to DataPulse and is
separate from any hospital database password. You can replace/revoke it in the UI.
Registration does not connect a database or transfer patient information. Field
review, patient matching and patient history remain labelled, session-only previews.

`GET /health/live` reports process liveness; `GET /health/ready` checks database
connectivity and migration revision. `/docs` shows the implemented OpenAPI contract.

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy src
```

SQLite is used only for fast unit/migration tests. PostgreSQL integration tests run
when `DATAPULSE_TEST_DATABASE_URL` points to a dedicated disposable database (see
development guide). CI supplies PostgreSQL and runs them automatically.

## Repository layout

`src/datapulse/central` owns the central app and relational foundation.
`src/datapulse/contracts` owns normalized schema contracts.
`src/datapulse/connectors` owns the source access interface.
`migrations` owns central schema history. `tests` contains unit and integration
checks; `infra/demo` records the future demo deployment gate. Additional modules
are introduced only by their roadmap milestone.

`web/` contains the React/TypeScript interface. Docker builds it automatically.
For native setup, build the interface before starting the backend (Node 24):

```powershell
Set-Location web
npm.cmd ci
npm.cmd test
npm.cmd run build
Set-Location ..
```

For interface development, `npm.cmd run dev` inside `web/` starts a local preview
on port 5173 and proxies health and `/v1` APIs to the backend on port 8000. For this
development mode, set the backend `DATAPULSE_BROWSER_ORIGIN` to
`http://127.0.0.1:5173` and restart it; use port 8000 for the built workspace.
