# M4: local schemas and mapping proposals

Implemented: read-only schema scans, immutable local registry, verified R4 core
catalog, declared FK graph, lexical classification, bounded candidate retrieval,
typed proposal validation and an Ollama adapter. This produces unapproved field
proposals, not executable assemblies or clinically validated FHIR resources.

## Prerequisites and pins

Python 3.12 environment from README; the two accepted fictional EHR environments
from [source startup](../infra/demo/README.md). Start Docker Desktop first. Keep all
DB credentials in the generated ignored `.tmp/m3-demo` files.

The tracked [FHIR lock](../src/datapulse/mapping/fhir.lock.json) pins
`hl7.fhir.r4.core#4.0.1`, archive SHA-256 and size. The package manifest declares no
dependencies. Cache/download failure or checksum mismatch stops catalog use.
BD-Core is outside demo scope.

The [local model lock](../src/datapulse/mapping/local-model.lock.json) pins the
observed Ollama 0.33.2 runtime and `qwen2.5-coder:3b` artifact digest. This model was
already installed; no model download was needed. Different installed artifacts
require a deliberately updated configuration and evaluation. The model is a demo
choice behind a provider interface, not an architecture dependency.

## Cache and provision

From the project root:

```powershell
.venv\Scripts\python.exe -m datapulse.mapping catalog --cache data/fhir
.venv\Scripts\python.exe -m datapulse.mapping registry-init --registry data/hospital/openmrs.sqlite
.venv\Scripts\python.exe -m datapulse.mapping registry-init --registry data/hospital/openemr.sqlite
```

M4 introduced hospital revisions `hospital_0001` and `hospital_0002`; current explicit
provisioning also applies ADR-020 `hospital_0003` for evidence/read audit. Opening an
absent/outdated registry fails. It does not create tables
on application startup or modify the central migration head `0002_access`.
Keep each hospital's registry and cached evidence under local per-user access
controls. Ignored `data/` is local storage, never a patient export for source control.

## Scan and save

This workspace already has verified source scans, separate registries, selected-field
files and unapproved proposals under `data/hospital/`. To inspect/reuse an existing
scan, load its receipt instead of scanning again:

```powershell
$scan = Get-Content data/hospital/openmrs-scan.json | ConvertFrom-Json
```

Use the proposal command below with that receipt. To capture a fresh observation:

```powershell
$scan = .venv\Scripts\python.exe -m datapulse.mapping scan --config .tmp/m3-demo/openmrs.json --credentials .tmp/m3-demo/credentials.json --registry data/hospital/openmrs.sqlite --output data/hospital/openmrs-schema.json | ConvertFrom-Json
$scan
```

Repeat using `openemr` paths for the other source. Stdout contains only scan ID,
source UUID, structural fingerprint and timestamp. Full metadata goes to the local
registry and optional output file, not operational logs. Repeated scans always
retain observations; unchanged structure shares a snapshot. Comments/defaults remain
associated with each individual scan. Every observation is read twice and compared;
this detects observed changes but does not claim transactional DDL snapshot isolation.

Optional `--policy` accepts a JSON ScanPolicy. Defaults: 1,000 base tables, 30,000
columns, 16,000,000 metadata bytes per observation and a 60-second deadline, plus
configured per-socket timeouts. Empty `tables` means all base tables in the exact
configured DB. A nonempty list must match case-preserving table names exactly.
Views and inferred relationships are excluded. Missing scope, limits, changed
metadata and driver errors fail safely; nothing is silently truncated.

## Propose selected fields

Create an ignored local file `data/hospital/openmrs-fields.json`:

```json
[
  {"table":{"namespace":"openmrs","name":"person"},"column":"birthdate"},
  {"table":{"namespace":"openmrs","name":"person"},"column":"gender"}
]
```

```powershell
.venv\Scripts\python.exe -m datapulse.mapping propose --registry data/hospital/openmrs.sqlite --source-id $scan.source_system_id --scan-id $scan.scan_id --package data/fhir/hl7.fhir.r4.core-4.0.1.tgz --model-config src/datapulse/mapping/local-model.lock.json --fields data/hospital/openmrs-fields.json --output data/hospital/openmrs-proposals.json
```

For OpenEMR, scan into its own registry and select `patient_data.DOB` and
`patient_data.fname` with namespace `openemr`. Select up to 40 explicit fields per
CLI run; oversized or wrong-source scopes are rejected. This M4 implementation
partitions to one field per model task, within the contract ceilings of 8 tables,
40 columns, 20 sample rows and 12 candidates. It defaults to 6 candidates and 2,048
output tokens. Current commands never read clinical rows or populate sample/profile
arrays. Unknown classifications/types or missing source-value evidence remain
unresolved.

Optional `--output` writes the proposed/unresolved results and their evidence to a
protected local JSON file for inspection. Keep that file in ignored hospital storage;
it is not a generic log or an approval action.

The registry retains proposed fields, exact target metadata, bounded task evidence,
confidence/rationale, required-field diagnostics and provider provenance. stdout is
only a run/count/status summary with `approved:false`. `completed` means all selected
fields received valid proposals, not human approval or sync readiness.

Repeating a compatible proposal command returns the saved run with `reused:true`
and performs no inference. Reuse considers semantic metadata (including comments),
scope/fields, catalog digest, model/runtime/context, template and validation versions.
New scan timestamps alone do not invalidate it. Failed runs are not reused. Add
`--force` to create another attempt, including retrying unresolved fields in a partial
run. This is proposal reuse; M5 will implement reviewed mapping release reuse.

## Checks and evaluation

```powershell
$env:DATAPULSE_DEMO_TEST_DIR = 'X:\DataPulse\.tmp\m3-demo'
.venv\Scripts\python.exe -m pytest -m source_db --tb=no
.venv\Scripts\python.exe scripts/evaluate_m4.py --package data/fhir/hl7.fhir.r4.core-4.0.1.tgz --model-config src/datapulse/mapping/local-model.lock.json --output data/hospital/m4-evaluation.json
```

The benchmark uses six checked-in fictional metadata cases. It records exact model
pins, outcomes and timing; it does not read EHR records or certify clinical accuracy.
Unit tests use tiny synthetic definitions and a local fake HTTP server; the actual
official archive and installed model are separately verified by these local commands.
See [verification](VERIFICATION.md) and [external research](research/M4_FHIR_PROVIDER_GATE.md).

M5 human review/approval and release assembly, M6 transformation/ingestion/FHIR
instance validation, clinical profiling/extraction, identity and UI integration are
not implemented by M4.
