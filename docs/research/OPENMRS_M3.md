# OpenMRS M3 deployment gate

Research checked 2026-10-07. This note verifies upstream source and registry
metadata, not a completed local deployment. Only source deployment and connector
health are authorized in this slice; extraction, agents and clinical APIs are deferred.

## Exact candidate pins

Use OpenMRS Reference Application **3.7.1**, a non-RC tag dated 2026-07-13.
The annotated Git tag `be2d14d14ac95165aeef9fe77100d5eb2b7dbb19` resolves to
commit `a476fd609612394ff66fce0b4ce29e949b0cfaf9`.
[Tag listing](https://github.com/openmrs/openmrs-distro-referenceapplication/tags),
[tag API](https://api.github.com/repos/openmrs/openmrs-distro-referenceapplication/git/tags/be2d14d14ac95165aeef9fe77100d5eb2b7dbb19).

- Backend: `openmrs/openmrs-reference-application-3-backend:3.7.1@sha256:929cfe5dca5f221460e0f4a57abb9294614df5f74fbb3bb865e01b8dfe7a985b`.
  Linux amd64 manifest: `sha256:e580f813bcaef272867ba5cb2cf1677078841b0d3333a6121eb707d4489ab062`.
  [Publisher registry metadata](https://hub.docker.com/v2/repositories/openmrs/openmrs-reference-application-3-backend/tags/3.7.1).
- Database: `mariadb:10.11.7@sha256:27292753bb759cd22be72e3c8192f1259ef47010c8634b5da0bc886845efe9fd`.
  Linux amd64 manifest: `sha256:905dd2ee9f25eca4f8e916dfa9e008c817972bf3f9dde64bd0430952adeb8cb9`.
  This exact database version appears in the release Compose file.
  [Official registry metadata](https://hub.docker.com/v2/repositories/library/mariadb/tags/10.11.7),
  [release Compose](https://github.com/openmrs/openmrs-distro-referenceapplication/blob/a476fd609612394ff66fce0b4ce29e949b0cfaf9/docker-compose.yml).

The distribution selects OpenMRS core **2.8.8**, Initializer **2.12.0**, REST
**3.5.0**, reference demo data **2.6.1**, reference content **1.4.0** and demo
content **1.9.2**. These are source declarations; inspect installed artifacts to
confirm image contents. Its Dockerfile uses moving `2.8.x` base images and Maven
snapshot tooling, so rebuilding that Git commit alone is not a reproducible image
build. Consume the published digest above.
[Distribution POM](https://github.com/openmrs/openmrs-distro-referenceapplication/blob/a476fd609612394ff66fce0b4ce29e949b0cfaf9/distro/pom.xml),
[Dockerfile](https://github.com/openmrs/openmrs-distro-referenceapplication/blob/a476fd609612394ff66fce0b4ce29e949b0cfaf9/Dockerfile).

## Minimal local source topology and initialization

Run backend plus its dedicated MariaDB. Omitting frontend/gateway is an inference
from upstream dependencies: backend requires only DB; frontend/gateway serve and
route browser assets. Expose backend 8080 and database only on loopback if host-side
checks require them. Keep source volumes, roles and network separate from central
PostgreSQL and OpenEMR. Backend data is `/openmrs/data`; DB data is `/var/lib/mysql`.
The release starts with table creation and automatic migrations enabled and
utf8mb4/general-ci database configuration.
[Release Compose](https://github.com/openmrs/openmrs-distro-referenceapplication/blob/a476fd609612394ff66fce0b4ce29e949b0cfaf9/docker-compose.yml).

Set `OMRS_CONFIG_CONNECTION_SERVER`, `OMRS_CONFIG_CONNECTION_DATABASE`,
`OMRS_CONFIG_CONNECTION_USERNAME`, `OMRS_CONFIG_CONNECTION_PASSWORD`,
`OMRS_CONFIG_AUTO_UPDATE_DATABASE=true`, `OMRS_CONFIG_CREATE_TABLES=true`, and
`OMRS_CONFIG_MODULE_WEB_ADMIN=true`. Override administrator bootstrap password with
`OMRS_CONFIG_ADMIN_USER_PASSWORD`; never rely on upstream defaults. Default DB driver
is MySQL; `OMRS_CONFIG_DATABASE=mariadb` selects the MariaDB driver. Keep secrets in
ignored local configuration. `OMRS_JAVA_MEMORY_OPTS` controls JVM allocation.
The administrator password must include upper- and lower-case letters (observed
installer rejection of a hexadecimal-only generated password); the demo generator
also ensures a digit and keeps the value whitespace-free. DB passwords use separate
random credentials and are unaffected by this application password policy.
Startup waits for database connectivity, starts Tomcat and requests `/openmrs/`
to trigger first initialization. A HTTP response alone does not prove DB schema
initialization or application authentication succeeded.
The pinned first installation was observed to raise a servlet-filter context
initialization error. Restart after installer completion before checking REST
authentication. This matches the [upstream first-start discussion](https://talk.openmrs.org/t/filters-and-or-servlets-cannot-be-added-to-context-openmrs-as-the-context-has-been-initialised/39187).
The bounded demo wait step detects context refresh completion and performs this
restart once; subsequent initialized starts use the persisted runtime configuration.
[Core startup configuration](https://github.com/openmrs/openmrs-core/blob/2.8.8/startup-init.sh),
[Core startup](https://github.com/openmrs/openmrs-core/blob/2.8.8/startup.sh).

## Controlled data and reset

Do not use randomized upstream patients as deterministic fixtures. Bundled module
2.6.1 returns without generating them when the exact runtime property
`referencedemodata.createDemoPatients=false` is set. Otherwise generation requires
positive global property `referencedemodata.createDemoPatientsOnNextStartup`.
For a fresh volume, extend `OMRS_JAVA_SERVER_OPTS` with
`-Dproperty.referencedemodata.createDemoPatients=false`, preserving its other
upstream JVM options. Core 2.8.8 `InitializationFilter` reads system properties,
strips the `property.` prefix into additional runtime properties, then merges
those into complete connection configuration before starting modules and saving
the runtime file. Do not precreate a runtime file containing only the seed flag:
`Listener` treats any runtime file as found and attempts database detection using
it, so missing connection properties can fail before scripted initialization.
`OMRS_EXTRA_` lowercases property names, so it cannot reliably set this camelCase
key. Existing initialized volumes require updating their complete runtime file;
the installation-script path is a first-initialization mechanism. Verify the exact
saved flag after startup. The upstream Initializer/demo content can independently load
metadata; count clinical tables after bootstrap before claiming an empty fixture.
[Pinned activator](https://github.com/openmrs/openmrs-module-referencedemodata/blob/b0faa08392959950bd17f5012e3fb86f172c13c6/api/src/main/java/org/openmrs/module/referencedemodata/ReferenceDemoDataActivator.java),
[runtime property handling](https://github.com/openmrs/openmrs-core/blob/2.8.8/startup-init.sh),
[installation property handling](https://github.com/openmrs/openmrs-core/blob/2.8.8/web/src/main/java/org/openmrs/web/filter/initialization/InitializationFilter.java),
[runtime discovery](https://github.com/openmrs/openmrs-core/blob/2.8.8/web/src/main/java/org/openmrs/web/Listener.java).

Deterministic patient/encounter/observation seed design remains deferred. Health
checks need no clinical rows. Reset should stop only the dedicated demo project,
verify its precise volume names, remove only its backend/DB disposable volumes,
then recreate pinned services and bootstrap configuration. Restart without volume
removal must preserve schema and credentials. Neither reset/restart behavior nor
zero clinical rows is verified by this research note.

## Schema, access, budget and license

Selected health-only seed variant: `openmrs-schema-health-3.7.1-v1`, using supported
`-Dinitializer.startup.load=disabled` to skip optional rich metadata domains while
the original core/module schema migrations and core administrative seed still run.
The full bundled OCL import was observed advancing but repeatedly fsyncing Lucene
indexes on this local Docker host. It was not an external network dependency.
Rich O3 terminology/forms completeness is deliberately outside this variant's
acceptance; future introspection/mapping fixtures must revisit their seed needs.

OpenMRS core uses joined person/patient identity (`patient.patient_id`), separate
patient identifiers and demographics, and observations with typed values and
concept relationships. The installed schema also contains distribution-module
tables, so source mappings cannot be inferred solely from core code.
[Patient mapping](https://github.com/openmrs/openmrs-core/blob/2.8.8/api/src/main/resources/org/openmrs/api/db/hibernate/Patient.hbm.xml),
[Person mapping](https://github.com/openmrs/openmrs-core/blob/2.8.8/api/src/main/resources/org/openmrs/api/db/hibernate/Person.hbm.xml),
[Obs mapping](https://github.com/openmrs/openmrs-core/blob/2.8.8/api/src/main/resources/org/openmrs/api/db/hibernate/Obs.hbm.xml).

A direct MariaDB read-only connector is suitable for this isolated source as a
project design choice. Provision a distinct account limited to SELECT on the exact
source database; test SELECT and denied INSERT/UPDATE/DELETE/DDL. Do not reuse the
OpenMRS application account, which needs schema/write privileges. Source credential
resolution stays connector-local. Actual allowlist metadata visibility and denial
tests are environment acceptance gates.

The full O3 production guide specifies 4 CPU cores, 8GB RAM and 100GB SSD minimum;
this is not measured guidance for our reduced demo. Proposed initial local caps:
backend 2GiB with JVM `-Xms256m -Xmx1536m`, DB 512MiB. Measure startup peak and steady
usage before declaring those sufficient alongside OpenEMR and central services.
Registry compressed amd64 sizes are approximately 697MB backend and 122MB DB;
unpacked images/volumes need more disk.
[Official deployment guide](https://o3-docs.openmrs.org/en-US/docs/recipes/deploy-to-production/).

Core 2.8.8 is MPL 2.0 with the OpenMRS healthcare disclaimer; preserve upstream
notices. Module dependencies have their own notices; this note does not claim one
license covers every bundled dependency.
[Core license](https://github.com/openmrs/openmrs-core/blob/2.8.8/LICENSE),
[Core notice](https://github.com/openmrs/openmrs-core/blob/2.8.8/NOTICE.md).

Gate status: source version, database pairing and registry digest pins verified.
Local pull, first initialization, artifact inventory, authenticated application
health, read-only role denial, restart/reset reproduction, empty clinical counts
and resource measurement require deployment evidence before connector completion.

## Initializer OCL import behavior

Initializer 2.12.0 supports offline OCL packages. Its `OpenConceptLabLoader` opens
each local ZIP with `new ZipFile(file)`, calls `importer.run(zip)`, and verifies a
new stopped import without an error message. This loader contains no remote URL
fetch. Bundled timestamped OCL ZIP filenames therefore do not demonstrate an
unpinned external dictionary dependency. Reference content 1.4.0 includes
versioned CIEL immunization and PD ZIP exports.
[Offline OCL documentation](https://github.com/mekomsolutions/openmrs-module-initializer/blob/2.12.0/readme/ocl.md),
[Pinned loader](https://github.com/mekomsolutions/openmrs-module-initializer/blob/2.12.0/api/src/main/java/org/openmrs/module/initializer/api/loaders/OpenConceptLabLoader.java),
[Reference content OCL files](https://github.com/openmrs/openmrs-content-referenceapplication/tree/1.4.0/configuration/backend_configuration/ocl).

Allow first metadata initialization to finish uninterrupted; schema existence or
an HTTP response alone is insufficient. The default `initializer.startup.load`
mode is `continue_on_error`, so startup can complete despite metadata errors.
Use `-Dinitializer.startup.load=fail_on_error` when validating a complete
distribution baseline. Domain filtering is explicitly supported through system
properties: `-Dinitializer.domains=!ocl` excludes the OCL domain;
`-Dinitializer.startup.load=disabled` suppresses all startup metadata loading.
Neither is necessary merely because ZIP imports are expensive. Such filters make
a customized schema-only variant, and dependent metadata may fail if required
concepts are omitted; record that distinction rather than claiming full reference
distribution initialization. No assertion that every bundled module avoids all
outbound network access follows from the OCL loader inspection.
[Pinned runtime controls](https://github.com/mekomsolutions/openmrs-module-initializer/blob/2.12.0/readme/rtprops.md).
