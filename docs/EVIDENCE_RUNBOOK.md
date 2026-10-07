# Fictional clinical evidence before hospital review

ADR-020 authorizes this first prerequisite slice: deterministic fictional fixtures,
bounded source-column profiles, relationship checks and immutable local evidence.
M5 mapping edits, human approval, coverage decisions and executable release assemblies
remain subsequent slices. M6 ingestion and M8 UI remain deferred.

## Seed and reset

Retain all source/image pins from `infra/demo/images.lock.json`. From the project root:

```powershell
.venv\Scripts\python.exe infra/demo/demo.py up
.venv\Scripts\python.exe infra/demo/demo.py wait
.venv\Scripts\python.exe infra/demo/seed_clinical.py
.venv\Scripts\python.exe infra/demo/seed_clinical.py verify
```

The seed operator is separate from the SELECT-only connector. It writes generated
fictional constants into upstream tables in the fixed `datapulse-m3-demo` project.
Every source has three fictional patients; two have deliberately similar names and
identifiers, one has missing demographics. Repeated encounters and typed observations
exercise clinical relationships. OpenEMR uses distinct `id`/`pid` and `id`/`encounter`
keys and one explicitly invalid orphan encounter for unmatched-key testing. OpenMRS
declared FKs remain enabled. No synthetic clinical schema or source-version change.

Seed repeats verify exact fixture columns/counts and make no additional writes.
Ignored per-source integrity receipts also detect changes to any unprojected owned
row column. Missing receipts with existing rows refuse recognition; recover by a
verified dedicated demo reset, not by adopting unknown rows. A crash after commit
but before receipt storage may require this reset.
Unexpected clinical rows, reserved-key collisions, changed metadata, missing installer
support identities or nontransactional tables refuse the operation. Per-source writes
are transactional; there is no atomic transaction across the two databases. A failure
can leave one verified source seeded; rerunning resumes only after checking both.
Read source restrictions in [seed research](research/M5_FICTIONAL_SEED_GATE.md).
Direct SQL fixtures bypass application creation services and are not an acceptance
test of clinical application workflows or equivalent application audit events.

The pinned OpenMRS EMR API module can fail on restart when its existing unknown
provider UUID has no matching core property. The launcher recognizes that exact
duplicate-UUID failure, checks pins and provider/property identity, fills only an
unset `provider.unknownProviderUuid`, then restarts once. Unexpected configuration
refuses recovery; provider rows and constraints stay intact. This is source-specific
demo bootstrap handling, not generic connector behavior. The primary source and
observed failure are recorded in the seed research note.

For a clean reset, use the existing `demo.py reset`, then `up`, `wait`, `provision`
and `seed_clinical.py`. Reset removes only dedicated fictional EHR volumes, preserving
central data and credentials. Existing hospital observations stay historical; collect
fresh evidence after reseeding. Verification accepts an empty baseline or an exact
recognized seed; arbitrary nonempty clinical data fails.

For automated verification after an accepted seed, run
`python infra/demo/reproduce_clinical.py --reset-fictional-sources`. It refuses unknown
data, resets only the dedicated EHRs, restarts/provisions/reseeds and compares complete
owned-row digests and structural fingerprints. Results are saved locally in ignored
`.tmp/m3-demo/clinical-reproduction.json`. Central data and evidence remain intact.

## Capture evidence

Explicitly upgrade each local registry before use. Existing observations are retained.

```powershell
.venv\Scripts\python.exe -m datapulse.mapping registry-init --registry data/hospital/openmrs.sqlite
.venv\Scripts\python.exe -m datapulse.mapping registry-init --registry data/hospital/openemr.sqlite
```

Current hospital head is `hospital_0003`; central migrations are unchanged. Use an
existing source scan receipt, or capture a fresh scan through the M4 runbook. Create
an ignored request file using its source UUID and structural fingerprint:

```json
{
  "contract_version": 1,
  "source_system_id": "0385fb0c-b004-4a57-9523-9e53fb9af033",
  "schema_fingerprint": "REPLACE_WITH_SCAN_FINGERPRINT",
  "profiles": [{"table":{"namespace":"openmrs","name":"person"},"columns":["gender","birthdate"]}],
  "relationships": [{
    "source_table":{"namespace":"openmrs","name":"encounter"},
    "source_columns":["patient_id"],
    "target_table":{"namespace":"openmrs","name":"patient"},
    "target_columns":["patient_id"]
  }]
}
```

```powershell
$scan = Get-Content data/hospital/openmrs-scan.json | ConvertFrom-Json
.venv\Scripts\python.exe -m datapulse.hospital capture --registry data/hospital/openmrs.sqlite --scan-id $scan.scan_id --config .tmp/m3-demo/openmrs.json --credentials .tmp/m3-demo/credentials.json --request data/hospital/openmrs-evidence-request.json --actor demo-reviewer --output data/hospital/openmrs-evidence.json
.venv\Scripts\python.exe -m datapulse.hospital inventory --registry data/hospital/openmrs.sqlite --scan-id $scan.scan_id --source-id $scan.source_system_id --output data/hospital/openmrs-coverage.json
```

OpenEMR's verified clinical relationship is `form_encounter.pid` -> `patient_data.pid`;
an `id` join should contradict the fixture. These are explicit requested checks,
not inferred or approved relationships. `actor` records the identified trusted local
operator; it is not a new authentication system or proof of the actor's identity.
Access is audited durably before reading rows, then completed/failed without bodies,
query parameters or credentials. A crash may retain a started event without completion.
If evidence persistence fails, no successful evidence summary is returned.

## Limits and interpretation

Requests select up to eight profile groups, forty total columns and eight relationships
with up to eight columns per key. Policy defaults: twenty sample rows, ten thousand
check rows per table, 256 bytes per scalar, 256 KiB serialized evidence, sixty seconds.
Limits are configurable within contract ceilings. Profiles use a primary-key prefix
or explicitly unordered prefix; they are not random or representative population
estimates. Truncation is explicit. Oversized values fail rather than silently crop;
DECIMAL values retain exact text, dates remain source text, binary values retain hex.

InnoDB repeatable-read snapshots are required for selected tables. Identifiers must
exist in a fresh source-bound scan and are quoted; values/limits are parameterized.
The source grant/TLS boundary is unchanged. Native database equality preserves source
collation/coercion semantics in composite-key checks. Counts include rows with any
null key, duplicate complete-key groups and unmatched non-null source rows.
Null keys require later reviewed optional/required policy. No linked record bodies
or arbitrary query interface is exposed.

Check complete tables only when both fit the configured row limit in the same snapshot;
otherwise emit `incomplete`, without population metrics. Duplicate target keys,
unmatched source keys or empty targets emit `contradicted`; otherwise `needs_review`.
Even complete passing evidence has `approved:false`; uniqueness/value overlap is not
semantic proof. A future human review must document purpose, cardinality, null policy
and exact evidence/version. Samples never authorize cross-hospital patient links.

Server execution limits supplement socket timeouts and overall deadline checks.
Metadata observations bracket capture to detect observed structural drift, without
claiming atomic DDL isolation or a future extraction cursor/revision token. Evidence
describes one snapshot only and cannot authorize a changed dataset automatically.
SQLite immutable evidence/audit remain subject to trusted file-owner limitations.
Protected ignored evidence output contains column values; generic logs/stdout do not.
M4 proposal commands continue metadata-only until explicit evidence integration.

The implemented inventory command exports every column from the exact immutable
scan as unresolved/awaiting human coverage review. It performs no source row reads
or automatic clinical exclusions. Recording reviewed coverage dispositions is M5.

## Following slices and acceptance

M5 must inventory every scanned column; Patient comes first and every remaining clinical
domain stays required tracked work. Humans explicitly resolve/exclude fields with reasons;
operational exclusions never silently hide clinical data. Build immutable edits, review
events, assemblies and releases, binding approval to exact digests and rejecting stale
or concurrent review. Release coverage is explicit. Complete interoperability is not
claimed until clinical coverage and later runtime/validation gates pass.

Run backend tests, lint and type checks from DEVELOPMENT.md. Source integration tests
require the pinned exact fixture. Tests must cover null/duplicate/unmatched/composite
keys, bounds, schema/source mismatch, snapshot restrictions, audit persistence,
migrations, seed collision/refusal and exact repeat behavior. Verification results
are recorded in VERIFICATION.md; implementation scope is narrower than full M5.

Database behavior references: [MariaDB snapshots](https://mariadb.com/docs/server/ha-and-performance/standard-replication/enhancements-for-start-transaction-with-consistent-snapshot),
[transaction syntax](https://mariadb.com/docs/server/reference/sql-statements/transactions/start-transaction),
[statement limits](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/query-optimizations/aborting-statements).
