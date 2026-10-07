# M4 FHIR catalog and local provider research gate

Reviewed 2026-10-07 against primary sources. This note verifies external contracts;
it does not claim that catalog checks validate complete FHIR resource instances or
that model-generated mappings are approved. ADR-018 selects global core R4 only;
BD-Core is outside this demo.

## Verified FHIR package artifact

The permanent [HL7 R4 downloads page](https://hl7.org/fhir/R4/downloads.html)
links `hl7.fhir.r4.core` as the conformance-resource NPM package. Its official
artifact URL is
[R4 core archive](https://hl7.org/fhir/R4/hl7.fhir.r4.core.tgz).
Downloaded and inspected in this workspace on the review date:

- Package: `hl7.fhir.r4.core#4.0.1`.
- Archive bytes: `4531911`.
- Measured SHA-256:
  `b090bf929e1f665cf2c91583720849695bc38d2892a7c5037c56cb00817fb091`.
- Manifest `package/package.json`: `name=hl7.fhir.r4.core`, `version=4.0.1`,
  `fhirVersions=["4.0.1"]`, `type=fhir.core`, `license=CC0-1.0`.
- Manifest has no `dependencies` field: no package dependencies are declared by
  this artifact. This does not establish that every external terminology named
  by a binding is included or freely licensed.
- Archive contains `4742` members. Inspected Patient and Observation definitions
  both have `version=4.0.1` and `fhirVersion=4.0.1`, with snapshots of 45 and 50
  elements respectively.

The checksum above is our measured artifact pin, **not an HL7-published signature
or asserted official checksum**. Download provenance is the official HTTPS URL;
subsequent cache/import operations must compare bytes with this exact pin and
reject mismatched manifest/version/dependencies. Do not silently replace the
digest when upstream bytes change. Cache locally and record the package identity
and digest in every proposal context.

The local inspected copy is `.tmp/m4-research/hl7.fhir.r4.core-4.0.1.tgz` (ignored
research artifact, not a source credential or patient export).

## Catalog semantics and implementation implications

[StructureDefinition](https://hl7.org/fhir/R4/structuredefinition.html) contains
the ordered element definitions; a snapshot carries inherited structure rather
than only differential changes. Use published snapshots, retain canonical URL,
version, kind, abstract flag and derivation, and distinguish resource definitions
from datatype definitions. Element IDs matter because profile slices can share a
path. Do not equate flat path lists with independent resource fields.

[ElementDefinition](https://hl7.org/fhir/R4/elementdefinition-definitions.html)
defines dot-separated paths, minimum/maximum cardinality, permitted type codes,
profiles, reference targets, content references and terminology bindings. Retain
`type.profile` and `type.targetProfile` separately: the latter identifies allowed
Reference/canonical targets. A `contentReference` imports another element's rules;
do not treat missing local types as an unrestricted target. Bindings retain their
strength and canonical ValueSet, including an explicit `|version` suffix.

[FHIR formats](https://hl7.org/fhir/R4/formats.html) specifies that choice paths
ending `[x]` serialize with the selected type's title-cased suffix. Catalog
`Observation.value[x]` therefore permits `valueQuantity` only when `Quantity` is
an allowed type. Repeated elements require explicit array/group metadata.
Complex datatypes contribute their own children: `Patient.name.family` requires
resolving the `HumanName` definition; it is not listed as a direct child in the
Patient snapshot. Bound traversal depth and prevent recursive datatype cycles.

Observed package examples: `Patient.name` is `0..*` HumanName;
`Patient.gender` is `0..1` code with required binding
`http://hl7.org/fhir/ValueSet/administrative-gender|4.0.1`;
`Observation.subject` permits Patient, Group, Device or Location references;
`Observation.value[x]` permits Quantity and ten other types.

[Terminology rules](https://hl7.org/fhir/R4/terminologies.html) distinguish a
CodeSystem namespace from a ValueSet and distinguish required, extensible,
preferred and example bindings. Persist those facts; accepting a candidate path
does not validate a proposed clinical code. External terminology validation and
licenses need explicit configuration rather than an automatic public-service call.
[FHIR validation](https://hl7.org/fhir/R4/validation.html) separates structure,
cardinality, values, terminology and other validation concerns. M4 proposal checks
must be described as catalog/contract validation; the later official validator
adapter is still needed for complete resource validation.

## Local structured provider contract

The official [chat API](https://docs.ollama.com/api/chat) accepts `model`,
`messages`, `format`, `options`, `stream` and `keep_alive`. Use `POST /api/chat`
with `stream=false`, a JSON Schema object in `format`, bounded generation options
and no tool definitions. Read the assistant's `message.content` as JSON only
after checking transport status and completion.

[Structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
documents supplying a schema in `format`, including that schema in the prompt,
and validating the resulting JSON with a separate application model. Grammar
constraint is insufficient to establish source ownership, valid candidate IDs,
evidence, supported transformations or semantic correctness. The documentation
states cloud structured outputs are unsupported; this adapter targets local use.

[Model listing](https://docs.ollama.com/api/tags) returns model name, full digest,
size, family and quantization metadata. Pin an explicit installed model tag **and
its observed full digest**; verify the digest before a call instead of trusting a
mutable tag. The [model-details endpoint](https://docs.ollama.com/api-reference/show-model-details)
is `POST /api/show` and exposes model capabilities, parameters, license and model
context metadata. Review the actual selected model's license. The
[version endpoint](https://docs.ollama.com/api-reference/get-version) and
[upstream route definitions](https://github.com/ollama/ollama/blob/main/server/routes.go)
identify `GET /api/version`; pin and verify the installed server version too.
These research sources do not select or invent a local model/version pin.

[Modelfile parameters](https://docs.ollama.com/modelfile) document `num_ctx`,
`num_predict`, `temperature` and `seed`. Set finite context/output limits and
record values per run; fixed seed and zero temperature do not replace evidence
or human review. [Context guidance](https://docs.ollama.com/context-length)
warns that larger contexts consume more memory. Our bounded task must fit the
explicit configured context, rather than inherit hardware-dependent defaults.

[Ollama FAQ](https://docs.ollama.com/faq) documents default loopback binding
`127.0.0.1:11434` and cloud-disable configuration. Require an explicit local
endpoint and installed local model for the demo; a loopback HTTP address alone
does not establish that the selected model avoids cloud execution. Credentials,
connection strings and arbitrary SQL never enter model tasks. No patient samples
are needed for this metadata-only milestone.

[API errors](https://docs.ollama.com/api/errors) documents non-success statuses
and JSON error bodies. Client connect/read/deadline timeouts, body-size limits,
safe error categories and bounded repair attempts are DataPulse policies, not
promised server-enforced API parameters. Do not log request/response bodies or
raw error strings. Model absence, version/digest mismatch, timeout, invalid JSON,
unfinished output and application-contract rejection all fail safely.

## Gate conclusions

The core archive identity, bytes, checksum and undeclared dependency state are
verified. Its snapshots support bounded typed candidate retrieval without an
implementation guide. Official Ollama structured-output endpoints support a
replaceable local provider, subject to observed installed version/model pins and
real bounded-call verification during acceptance. Neither this package gate nor
provider output grants mapping approval or authorizes synchronization.

## MariaDB read-only metadata visibility

Investigated after the accepted SELECT-only demo users returned no
`information_schema.TABLE_CONSTRAINTS` rows despite visible tables and indexes.
This is documented here as a prerequisite finding, not a reason to widen grants.

Pinned upstream sources
[MariaDB 10.11.7 sql_show.cc](https://github.com/MariaDB/server/blob/mariadb-10.11.7/sql/sql_show.cc#L7306)
and
[MariaDB 12.3.3 sql_show.cc](https://github.com/MariaDB/server/blob/mariadb-12.3.3/sql/sql_show.cc#L7719)
explicitly filter both `TABLE_CONSTRAINTS` and `REFERENTIAL_CONSTRAINTS` on at
least one non-SELECT table/column privilege (`TABLE_ACLS & ~SELECT_ACL`). Their
`KEY_COLUMN_USAGE` handlers accept table privileges including SELECT. Therefore
an empty constraint table under these reader accounts does not establish that
declared keys or relationships are absent.

The official
[KEY_COLUMN_USAGE definition](https://mariadb.com/docs/server/reference/system-tables/information-schema/information-schema-tables/information-schema-key_column_usage-table)
provides constraint name, source column, ordinal position and referenced schema,
table and column. Use these actual declarations directly for ordered FK edges,
filtering `REFERENCED_TABLE_NAME IS NOT NULL`, without an inner join to the hidden
`TABLE_CONSTRAINTS` rows. Obtain primary/unique index column order from the visible
`STATISTICS` metadata. Keep update/delete actions unknown when hidden; this slice
needs declared edges, not guessed referential actions. Include table identity in
constraint grouping: MariaDB 12.1+ permits repeated constraint names on different
tables, as documented in
[MariaDB constraints](https://mariadb.com/docs/server/reference/sql-statements/data-definition/constraint).

[SHOW CREATE TABLE](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/show/show-create-table)
requires SELECT and can reveal declared FK clauses without expanded privileges.
Its output depends on SQL_MODE, and the documentation distinguishes declaration
from physical metadata. It is an optional separately bounded parsing route when
referential actions are required; do not add an unrestricted DDL parser or broader
grants merely to populate fields outside the current introspection contract.
