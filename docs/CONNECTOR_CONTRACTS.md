# Hospital-side connection contracts

ADR-020 expands source access through a separate `MySQLEvidenceReader.capture` port.
Requests bind source UUID, exact scan fingerprint, selected columns and composite
relationship keys. Schema allowlists, InnoDB snapshots, row/value/byte/time bounds and
native DB equality checks precede immutable hospital persistence. It implements
bounded evidence alone, not the broader extraction/cursor protocol. No relationship
is approved by this port. See [evidence contracts/runbook](EVIDENCE_RUNBOOK.md).

Implemented M3 connection/health (ADR-017) and metadata-only introspection (ADR-019).
The broader `DatabaseConnector` profile/extraction methods remain future work;
an introspection adapter does not pretend to implement them.
No new central or hospital HTTP endpoint is introduced.

## Configuration and credentials

Hospital-local immutable `ConnectionConfig` version 1 binds one source UUID,
vendor (`mysql`/`mariadb`), host/port, exact database name, opaque credential reference,
TLS policy and bounded connect/read/write timeouts (1–30 seconds). Extra fields
are rejected, including raw SQL or inline credentials. EHR product is absent.
The demo uses two independent fixed fixture UUIDs; actual deployments use registered
source UUIDs. Configuration is neither sent to models nor stored centrally.

`CredentialResolver.resolve(reference)` returns the bound source UUID, username
and secret password. A mismatched credential source is rejected before DB access.
The local demo resolver reads an explicitly selected, size-bounded JSON file with
exact reference keys; it never turns reference text into filesystem paths. Password
representation and serialization remain redacted. Resolution happens for each fresh
health connection so credential updates are not cached indefinitely. Files require
local per-user access controls; deployment secret-manager adapters can replace this
resolver without changing DB adapter or source models.

Default TLS policy is `verify_identity`, requiring a CA file, hostname/certificate
verification and TLS negotiation before sending authentication. A server without TLS
must fail closed, rather than downgrade. `disabled_local_demo` is explicit and
restricted to literal loopback addresses; remote plaintext is rejected. Demo stacks
do not configure server TLS, so verification-mode checks against them must fail.

## Connection health boundary

`ConnectionProbe.check()` opens a fresh authenticated connection to the configured
database, uses fixed metadata queries, checks the selected database and vendor,
verifies only SELECT/USAGE grants confined to that database, and closes all resources
before returning. No automatic retry, pooling or retained socket. DB grants enforce
read-only access; a read-only transaction supplements this and does not replace it.
The caller cannot supply SQL, patient IDs or table names.

`ConnectionHealth` v1 carries source UUID, status, checked UTC timestamp, elapsed
milliseconds and a bounded failure category. Health reports omit host, username,
database password, raw exceptions/SQL and patient bodies. Every request failure
becomes a category, not a raw driver traceback. A healthy result means authenticated,
database-scoped read-only access at that time; it makes no schema/FHIR/clinical claim.
Closed/unavailable probe dependencies report failure without inventing success.

CLI JSON stdout contains only these reports; errors exit nonzero. Config-file
validation errors are redacted rather than printing submitted input. Core adapter
selection uses vendor only; OpenMRS/OpenEMR names appear solely in demo tooling.

## Acceptance and deferred work

Both pinned EHR installations must reproduce and pass fixed version/empty-baseline
checks before writing/testing vendor adapters. Tests then exercise success for each,
credential rotation, missing reference, incorrect password, unavailable server,
wrong database/vendor, TLS rejection, insufficient or excessive privileges, resource
cleanup and secret-free errors. Integration fixtures attempt rejected DML/DDL on
known test tables inside transactions; they never intentionally write source records.
Observed acceptance: both actual pinned EHR source tests pass; file credential
rotation/source binding/cleanup are unit-tested. Remote verified-TLS success and
production secret-manager provisioning remain unverified environment concerns.

Introspection followed environment and connection-contract acceptance. M4 proposals
are now implemented separately. ADR-020 bounded profiling/checks use their own port;
extraction/cursors and runtime drift remain deferred. Connections
do not mutate central registration status or use central connector bearer tokens.

## Implemented metadata scan boundary

`SchemaScanner.introspect(source_system_id)` returns `DatabaseSchema` v1 for base
tables in the exact configured database. `ScanPolicy` adds optional exact table
allowlists, table/column counts, metadata byte bounds and a scan deadline. It shares
the verified source-bound read-only socket/grant/TLS checks with health. Every query
is fixed INFORMATION_SCHEMA SQL, with database and internal row limits parameterized.
No clinical table rows or caller-supplied SQL are accessed.

Capture native types, ordinals/nullability, keys/unique/index column order, declared
foreign keys and case-preserving identifiers. Out-of-scan FK targets remain visible;
unknown types remain unknown and no relationships are inferred. MariaDB's SELECT-only
visibility requires reading KEY_COLUMN_USAGE directly, without joining the hidden
TABLE_CONSTRAINTS view. Observe metadata twice and reject disagreement. Socket/read
limits apply alongside the overall deadline; this does not promise transactional DDL
isolation. A streaming limit failure closes without draining a large result, using
tested cleanup for the pinned driver. Registry persistence belongs to the hospital
module, not the connector or central API. See [runbook](M4_RUNBOOK.md).
