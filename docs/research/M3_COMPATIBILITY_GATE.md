# M3 compatibility gate

Scope accepted 2026-10-07: M2 closeout, upstream research and reproducible EHR
environments, then generic authenticated read-only database connection/health
checks. Introspection follows successful environment/connection-contract testing;
mapping, Agent 1 and later milestones were deferred in this original connection
gate. ADR-019 subsequently authorizes metadata introspection and M4 proposals.

## Verified source selection

The [OpenMRS research](OPENMRS_M3.md) and [OpenEMR research](OPENEMR_M3.md)
trace exact versions, configuration, seeds/resets, schema traits, resources,
licensing and connector requirements to official source and registry metadata.
The [image lock](../../infra/demo/images.lock.json) and
[Compose configuration](../../infra/demo/compose.yaml) choose immutable artifacts.
Do not replace digest locks with current tags: upstream version tags are rebuilt.

Fictional source A runs OpenMRS Reference Application 3.7.1/core 2.8.8 on MariaDB
10.11.7. Fictional source B runs OpenEMR 8.4.1/schema 543 on MariaDB 12.3.3.
The selected MariaDB 12.3.3 index is the official digest resolved on 2026-10-07,
explicitly different from the older same-version digest in upstream Compose.
Actual initialization must validate this pairing before connector implementation.

Each source owns an independent network, database volume, installer/application
account and SELECT-only connector identity. Central PostgreSQL, source registrations
and central connector bearer credentials remain separate. Product labels belong
to demo configuration, not branches in the core connector adapter.

## Seed and access decisions

The versioned baseline is each upstream installer with schema/core reference/admin
metadata and zero clinical patient rows. OpenMRS uses `openmrs-schema-health-3.7.1-v1`
with the optional rich metadata/terminology loader disabled through supported
`-Dinitializer.startup.load=disabled`. Core and module schema migrations still run;
rich O3 demo metadata, clinical forms and terminology functionality are not accepted
in this slice. The full metadata load was observed importing bundled OCL ZIPs and
performing Lucene fsync; no live terminology download was required. OpenMRS's random patient generator is
explicitly disabled using its exact installer property. Clinical fixtures are a
later separately versioned slice, not required for authenticated DB health.

Direct DB SELECT is suitable for this isolated demo. It bypasses EHR application
ACL/audit semantics and depends on a particular schema; it does not establish
production clinical export suitability or an upstream stable schema guarantee.
Future introspection must preserve OpenMRS person/patient joins, concepts and typed
observations, and OpenEMR binary UUIDs, logical references without declared FKs and
external documents. These are research findings, not implemented introspection.

## Reproduction and resources

The [runbook](../../infra/demo/README.md) defines init/start/verify/provision and
restart/reset. Passwords are generated locally in ignored files, never passed as
CLI arguments or saved centrally. Source ports bind only to loopback. Plaintext DB
transport is explicit isolated local demo policy; remote use requires verified TLS.
Reset removes only this project's five source volumes and retains local credentials,
then reruns the same installers and reader grants. Installer timestamps/UUIDs/salts
may differ: reproducibility means the same schema/version and zero-patient baseline.

The current Docker engine supplies 16 CPUs and about 7.68 GiB RAM. Compose caps
combined source services at 6 vCPU and 5.5 GiB RAM: OpenMRS backend 2.5 GiB,
OpenEMR 1.5 GiB, two databases 0.75 GiB each. These are engineering budgets,
not upstream certified minimums. Plan at least 20 GiB free Docker storage for both
reduced stacks as an initial estimate. Record actual image/volume/steady memory
usage and bootstrap observations; full O3 production requires more resources.

## Completion evidence

Primary-source research and registry digest resolution are complete. Two clean
installations of the selected schema-health baseline passed on 2026-10-07 before
connector code began. Both source applications became ready with exact installed
versions and zero clinical rows. The second reset removed all five demo volumes,
retained local credentials and recreated the same baseline. Separate SELECT-only
source identities were provisioned only after verification passed. Resource
observations follow below. The source-environment gate is complete. Contract/adapter tests
passed for both authenticated health checks, denied writes, wrong credentials,
wrong database/vendor, missing references, TLS policy and unreachable server failures
with secret-free reports. Final backend suite: 88 passed including PostgreSQL and
both source DB integrations. A third clean start verified the launcher's specific
first-install error detection; both standalone source checks returned healthy.
A healthy connection is not schema/clinical conformance.

First accepted clean schema-health initialization on 2026-10-07: OpenMRS authenticated
REST session succeeded, core artifact 2.8.8, MariaDB 10.11.7, exact saved random-patient
disable flag and zero Patient/Encounter/Obs counts. OpenEMR readiness succeeded,
version 8.4.1/schema 543, MariaDB 12.3.3 and zero patient_data rows. Both original
installers created their databases; a second clean reset reproduced these results.
OpenMRS emits optional address-hierarchy/XML configuration warnings in this reduced
baseline; full module metadata/functionality is not claimed. The same digest contains
the bundled offline OCL archives even though their optional loader is disabled.

The four downloaded images' Docker-reported sizes were 697,099,402 bytes (OpenMRS),
674,595,049 bytes (OpenEMR), 122,480,175 bytes (MariaDB 10.11.7) and 107,853,882
bytes (MariaDB 12.3.3). These are image-store reported sizes, not total Docker disk
capacity requirements. Bootstrap snapshots observed OpenMRS at 715–804 MiB,
OpenMRS DB at 213–227 MiB, OpenEMR at 71–79 MiB and OpenEMR DB at 176–179 MiB;
these sampled observations are not measured maximum/production minimums. The
initial source startup plus automatic OpenMRS restart completed within the 15-minute
bound on both accepted clean runs with these limits. Reserve additional disk/memory
for unpacked layers, transient work, volumes, central services and host overhead.

Accepted-run steady snapshot: OpenMRS 1.164 GiB, OpenMRS DB 237.5 MiB,
OpenEMR 74.27 MiB and OpenEMR DB 179.1 MiB. Volume directory usage was 272,912 KiB
(OpenMRS DB), 442,340 KiB (OpenMRS data/modules/index), 247,364 KiB (OpenEMR DB),
480 KiB (OpenEMR site state) and 36 KiB (OpenEMR logs). These observations cover
this empty schema-health seed, not future clinical/terminology workloads.
