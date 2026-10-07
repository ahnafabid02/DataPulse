# ADR-017: Pinned demo environments and generic source connection checks

Accepted 2026-10-07 following explicit user confirmation after M2 closeout.
This expands the M2-only scope of ADR-016 to the first M3 slice.

Complete a primary-source research/compatibility gate for exact OpenMRS/OpenEMR
versions, database versions, digest-pinned Docker images, startup, local credential
configuration, schema characteristics, direct DB suitability, resource budgets,
controlled seeds, reset and licensing before writing connector code. Reproduce the
source environments before testing connectors against them. Published image digests
pin the demo artifacts; changing a version/digest requires re-running the gate.

Run two independently installed EHR source databases. An empty clinical baseline
with installer-provided reference/admin metadata is sufficient for this slice;
future deterministic patient fixtures must be explicitly fictional and versioned.
EHR installers may write their own database. DataPulse connectors use separately
provisioned SELECT-only identities scoped to one source database. Credentials and
TLS settings belong in hospital-local configuration and credential references, never
central registrations or model tasks. Local-only container networking may use an
explicit plaintext demo policy; remote connections require verified TLS.

The connector connection/health interface is distinct from the future introspection,
profiling and extraction interface. Vendor adapters own fixed bounded health queries,
credential resolution, timeouts, resource cleanup and safe failure categories. No EHR
product branching, arbitrary SQL entry point or pretend clinical endpoint is added.
Health proves authenticated access to the configured database and read-only policy;
it does not mean schema compatibility, mapping correctness or clinical readiness.

Acceptance: both source environments start/reset reproducibly; both connectors
authenticate and report health; denied writes and credential/network/database/TLS
failures are exercised with secret-free reports. Keep source identities separate.
Schema introspection may begin only after these environments and contracts are
tested. Profiling/extraction/drift remain later M3 work. M4–M9, mapping and Agent 1
reasoning remain deferred. FHIR R4 4.0.1 and source-preserving identity/provenance
decisions remain in force.

ADR-019 subsequently authorizes metadata scans, the local schema/proposal registry
and M4; the deferred boundary above records the original connection slice.
