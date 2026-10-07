# Reproducible fictional EHR source demo

This first M3 slice installs two pinned EHRs and proves DB connection health.
Read [the compatibility gate](../../docs/research/M3_COMPATIBILITY_GATE.md), the
source research and [image lock](images.lock.json) before changing these images.
Schema introspection, mapping, extraction and Agent 1 remain deferred.

## Startup

Use Python 3.12 with the repository environment, Docker Engine/Compose and Linux
amd64 containers. From the repository root:

```powershell
.venv/Scripts/python.exe infra/demo/demo.py init
.venv/Scripts/python.exe infra/demo/demo.py up
.venv/Scripts/python.exe infra/demo/demo.py wait
.venv/Scripts/python.exe infra/demo/verify_environment.py
.venv/Scripts/python.exe infra/demo/demo.py provision
```

Downloads and first installation take several minutes. Repeat verification while
initialization is incomplete; nonzero exit means both environments are not yet
accepted. It checks fixed installer metadata and counts, not schema discovery or
patient bodies. Provision reader roles after verification succeeds.
The bounded `wait` step waits up to 15 minutes and performs one OpenMRS restart
after initial installation; modules that register servlet filters need this on
the pinned first start. Subsequent restarts retain complete installer configuration.

OpenMRS 3.7.1/core 2.8.8 uses MariaDB 10.11.7 at loopback port 13306, backend
port 8081. OpenEMR 8.4.1 uses MariaDB 12.3.3 at port 13307, web port 8082.
OpenMRS frontend/gateway are omitted; the backend still installs the actual EHR
schema. Both use original upstream installers and zero-patient clinical baselines
with core reference metadata. OpenMRS uses the supported
`initializer.startup.load=disabled` schema-health variant: it preserves actual core
and module migrations but omits rich demo metadata/terminology imports. Full O3
clinical forms/terminology workflows are not accepted by this connection demo.
No random or public patient dump is loaded.

## Source connection health

After verification/provisioning, use the same vendor adapter for each independent
source. The credential reference file stays hospital-local:

```powershell
.venv/Scripts/python.exe -m datapulse.connectors --config .tmp/m3-demo/openmrs.json --credentials .tmp/m3-demo/credentials.json
.venv/Scripts/python.exe -m datapulse.connectors --config .tmp/m3-demo/openemr.json --credentials .tmp/m3-demo/credentials.json
$env:DATAPULSE_DEMO_TEST_DIR = 'X:\DataPulse\.tmp\m3-demo'
.venv/Scripts/python.exe -m pytest -m source_db --tb=no
```

Use your checkout's absolute path for the test variable. A healthy JSON report
contains source UUID, UTC check time and elapsed milliseconds; failure uses a
redacted category and nonzero exit. No endpoint, username, SQL, password or patient
body is printed. Health proves DB authentication and restricted read permissions,
not clinical readiness. Metadata introspection and bounded evidence now have separate
hospital-local commands; see the M4 and evidence runbooks.

`init` generates independent random root/application/admin/connector passwords
in ignored `infra/demo/.env`. Root client config, source configs and credential
reference store live in ignored `.tmp/m3-demo`. OpenEMR's site volume also stores
DB settings. Restrict access to these local files/volumes. Never print rendered
Compose environments, installer output or secrets into chat/logs. Local Docker
administrators can inspect container environments. Generated passwords avoid
installer argument parsing issues. No source password enters central metadata.

Reader `datapulse_reader` receives SELECT only on its own source DB. Central
connector bearer keys are separate from these database passwords. Source UUIDs
in generated configs identify fixed disposable fixtures; a future hospital service
must use its corresponding registered UUID. Local health is not an API claim that
central registration has verified connectivity.

## Restart and reset

ADR-020 adds generated fictional clinical fixtures after installer acceptance:
`python infra/demo/seed_clinical.py`, then `seed_clinical.py verify`. The verifier now
accepts either the empty baseline or the exact recognized fixture; unexpected clinical
data is rejected. Repeats verify without adding records. After a clean reset/provision,
run the seed again. See [evidence runbook](../../docs/EVIDENCE_RUNBOOK.md) for source
limitations, missing/duplicate-looking data and the intentionally invalid OpenEMR join.

```powershell
.venv/Scripts/python.exe infra/demo/demo.py stop
.venv/Scripts/python.exe infra/demo/demo.py up
.venv/Scripts/python.exe infra/demo/demo.py wait
.venv/Scripts/python.exe infra/demo/verify_environment.py
```

Restart preserves source volumes and roles. Clean reset is explicitly destructive
only to this fictional demo:

```powershell
.venv/Scripts/python.exe infra/demo/demo.py reset
.venv/Scripts/python.exe infra/demo/demo.py up
.venv/Scripts/python.exe infra/demo/demo.py wait
.venv/Scripts/python.exe infra/demo/verify_environment.py
.venv/Scripts/python.exe infra/demo/demo.py provision
```

The launcher fixes project `datapulse-m3-demo` and its Compose file. It removes
only `datapulse-m3-demo_openmrs_db`, `datapulse-m3-demo_openmrs_data`,
`datapulse-m3-demo_openemr_db`, `datapulse-m3-demo_openemr_sites` and
`datapulse-m3-demo_openemr_logs`, plus that project's containers/networks.
It preserves central volumes and local credentials. OpenEMR DB and site state must
reset together. Never globally prune Docker or attach actual hospital volumes.
Installer timestamps/UUIDs/salts may differ; reset reproduces schema/version and
the same empty clinical baseline, not byte-identical database files.

## Resources and constraints

Combined caps: 6 vCPU and 5.5 GiB RAM. Initially plan 20 GiB free Docker storage;
these are reduced local demo budgets, not production minimum/capacity guarantees.
Research notes cover upstream requirements, notices and license constraints.
Keep ports loopback-only. Verified TLS, access, retention and deployment review
are required before remote or real clinical use.
