# OpenEMR M3 compatibility research

Reviewed 2026-10-07. Research findings and proposed demo procedure; installation,
resource use and connector behavior require the M3 integration run before acceptance.
This document does not authorize schema introspection, mapping or Agent 1.

## Version and image lock

Use OpenEMR **8.4.1**, released 2026-09-20, source tag `v8_4_1`, commit
`a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872`. Its release notes require PHP 8.3+
and MariaDB 10.11+ or MySQL 8.4+. Select MariaDB **12.3.3**, as used by the
versioned upstream production compose, rather than mixing in an untested engine.
[Release](https://github.com/openemr/openemr/releases/tag/v8_4_1),
[pinned compose](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/docker/production/docker-compose.yml).

Resolved official Docker Hub registry metadata during this research:

- `openemr/openemr:8.4.1@sha256:a2205ccbe3cbed02cccd4f4e9a32338dd1c68c26cd87ef8046802b5f65187803`
  is the multi-platform image index. Linux amd64 manifest:
  `sha256:66003136eb6f249f82295bcbb2f6545c9513ced5d9b7558b75cfa5e5a0c724e4`;
  arm64 manifest: `sha256:5b2ffa9d63cf7a0774a68c040ed60146958c457dc0907006218df82bd6146be3`.
- `mariadb:12.3.3@sha256:2bdff1534a7e569fecaf4b10b66ad0d410806e382d9db29ba305448addda97c4`
  is the current official multi-platform index. Linux amd64 manifest:
  `sha256:aed2b5ccc6356b54dda3b461e01584b420e549bb958cdfbf717ac22d75a84602`.
- The pinned upstream compose records an older immutable MariaDB index,
  `sha256:dd9b303aed4f4890ed09f766d8ca9ddfd176c0c6f6267feff53b3192ec65a979`.
  Either requires actual pull verification; use one chosen digest consistently
  in the lock, compose, tests and evidence, never substitute a tag during startup.

Registry sources:
[OpenEMR tag metadata](https://hub.docker.com/v2/repositories/openemr/openemr/tags/8.4.1),
[MariaDB tag metadata](https://hub.docker.com/v2/repositories/library/mariadb/tags/12.3.3).
OpenEMR tag last update was `2026-10-07T06:44:50.559538Z`; the versioned tag is
rebuilt, so the digest is essential. The release image pipeline fetches a release
branch; the source tag is the research reference, not proof that every file in the
daily-built image equals that commit. Inspect the running image version and record
its actual schema version before declaring the gate passed.
[Image pipeline](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/docker/README.md),
[Dockerfile](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/docker/release/Dockerfile).

## Reproducible startup and configuration

Adapt the pinned production compose into a dedicated DataPulse demo project with
separate DB, site and log named volumes. Use Linux containers (amd64 initially).
Keep the DB on the source network; if host-based connector tests need a port,
bind it to loopback only. Bind the EHR web UI to loopback on a dedicated port.
No central DB role or central source credential participates in this stack.

MariaDB starts with `mariadbd --character-set-server=utf8mb4`, a generated root
password, and its volume at `/var/lib/mysql`. Wait for the official
`healthcheck.sh --su-mysql --connect --innodb_initialized` check. Then start
OpenEMR with `MYSQL_HOST`, `MYSQL_PORT=3306`, `MYSQL_DATABASE=openemr`,
`MYSQL_ROOT_PASS`, `MYSQL_USER`, `MYSQL_PASS`, `OE_USER` and `OE_PASS`.
The root account is bootstrap-only; the application and connector use separate
accounts. Set values explicitly instead of upstream example default passwords.

The entrypoint runs `auto_configure.php` as the Apache user, installs the schema,
reference data and first administrator, saves site DB settings in
`sites/default/sqlconf.php`, and removes initial setup scripts once configured.
Persist `/var/www/localhost/htdocs/openemr/sites` and `/var/log`. Wait for EHR
readiness at `https://localhost/meta/health/readyz`, then provision the connector
role. The official guide estimates first startup at 5–10 minutes; use bounded
startup timeouts and retain sanitized diagnostic metadata on failure.
[Entrypoint](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/docker/release/openemr.sh),
[installer configuration library](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/docker/release/utilities/devtoolsLibrary.source),
[Docker guide](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/DOCKER_README.md).

Keep generated passwords in ignored hospital-local configuration or mounted secret
files, never checked-in compose values, central records, model inputs or logs.
The upstream entrypoint consumes environment values; a local launcher may read
secret files and inject them without printing them. Its installer splits a generated
configuration string into arguments, so generated bootstrap passwords should use
a conservative whitespace-free alphabet until special-character support is tested.
The connector credential resolver must support the actual password without URL
concatenation or logging. The site volume itself contains credentials and must stay
local. Use explicit TLS policy: loopback/private isolated local demo may permit
disabled DB TLS only as an explicit demo setting; remote deployments require
verification against a configured CA.

## Seed and reset

The health-only M3 seed is the upstream clean installation: schema, reference
configuration and administrator, **zero clinical patients**. This is a fictional
hospital environment and connection proof does not require clinical rows. Name
this baseline `openemr-clean-8.4.1-v1` and validate its version after every reset.
Do not claim that the production image loads demo patients. `DEMO_MODE` and
`SQL_DATA_DRIVE` are documented primarily for flex development images and are
not a verified seed route for this selected production image.
[Official image guidance](https://hub.docker.com/r/openemr/openemr),
[clean installation schema](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/sql/database.sql).

If later acceptance requires clinical examples, use a separate reviewed, immutable
fictional fixture with its checksum, exact import order and expected identifiers;
retest against this locked version before use. Public demo backups are unsuitable
as reproducible uncontrolled seed sources. The official demo farm supports named
SQL fixture imports but is a separate moving development deployment.
[Demo farm](https://github.com/openemr/demo_farm_openemr).

Reset only this dedicated project: stop its containers and remove **all three**
project-owned DB/site/log volumes together, then recreate with the same image
digests and regenerate/reload local credentials and connector grants. Resetting
only MariaDB leaves `sqlconf.php` and configured markers inconsistent with a new
DB. Never use a global Docker prune. Run successful authentication and health,
wrong-password and non-writable-role checks after two independent clean starts.
The reset operation is destructive only to the explicitly named fictional demo.

## Schema characteristics and direct DB suitability

The pinned `version.php` and `sql/database.sql` identify schema version **543**
and ACL version **14**. The schema uses InnoDB tables, integer/bigint local keys,
binary(16) UUIDs, text, decimal, date/datetime fields and per-table indexes.
`patient_data` has both a row ID and patient identity fields; `forms` carries
patient/encounter references plus `form_id`, while clinical forms occupy separate
tables. `lists` contains typed clinical entries. The checked-in schema contains
no declared `FOREIGN KEY` clauses: semantic relationships cannot be assumed to
be enforced FKs. Documents can be stored outside relational rows, so future DB
reads alone cannot claim a complete record export.
[Schema](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/sql/database.sql),
[version identifiers](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/version.php).

Direct authenticated read-only MariaDB access is suitable for this isolated
health-only demo. This is a DataPulse design choice, not an upstream stable
schema/API guarantee: it bypasses EHR application ACL/audit policy and therefore
cannot establish clinical production suitability. Grant the connector only
`SELECT` on this one source database; no root/application password, writes,
global metadata privileges or arbitrary caller-supplied SQL. Health executes a
fixed constant query with bounded connect/read timeouts and closes resources.
No runtime table discovery or clinical data query belongs in this milestone.

## Resources and licensing

No current official 8.4.1 minimum hardware specification was verified. For the
small clean demo, reserve **2 vCPU, 3 GiB RAM and 10 GiB free storage** for this
source stack as an engineering starting budget, not a tested requirement. Measure
actual peak bootstrap RSS, steady-state RSS and volume usage during acceptance.
Registry compressed sizes are about 675 MB for the amd64 EHR and 108 MB for
MariaDB; unpacked layers, temporary installation files and Docker Desktop VM
overhead need extra space. Budget separately for OpenMRS, central PostgreSQL and
the host. Do not extrapolate a health demo budget to clinical workload capacity.

OpenEMR is GPL v3; the image labels specify GPL-3.0-or-later. Keep notices and
the pinned corresponding upstream source reference if redistributing artifacts;
do not modify/repackage upstream binaries in this milestone. Docker Desktop
licensing depends on the user's organization and use; Linux Docker Engine is a
deployment alternative. An isolated fictional demo is not a production security,
clinical, regulatory or interoperability certification.
[OpenEMR license](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/LICENSE),
[Docker Desktop license](https://docs.docker.com/subscription/desktop-license/).

## Connector requirements carried to M3

- Generic MariaDB/MySQL protocol adapter; OpenEMR is source metadata, never a
  product branch in core connector logic.
- Hospital-local source ID, database name, endpoint/port, credential reference,
  TLS policy and bounded timeouts; preserve exact deployment identity.
- Authenticated connection and fixed-query health contract with sanitized typed
  failure outcomes; wrong credentials, unavailable server and timeout tests.
- Separate connector DB role and evidence that application/root credentials are
  unnecessary and connector writes are rejected.
- Repeatable initialization, version checks, grant provisioning and clean reset;
  preserve expected deployment/version metadata in acceptance evidence.
- Future introspection must distinguish indexes from relationship evidence,
  binary UUIDs from text, local patient IDs from row IDs, and external document
  storage. Those requirements are research findings only; introspection stays
  deferred until both environments and connector contracts pass the gate.
