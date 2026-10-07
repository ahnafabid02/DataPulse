# Domain model

All internal IDs are UUIDs, times UTC RFC3339, versions positive integers, source
keys opaque case-preserving strings. FHIR logical IDs use R4 syntax and are separate
from internal IDs. Contracts carry `contract_version`; breaking changes increment it.

## Organizations and sources

Organization: `id`, unique `code`, `name`, `created_at`. Identifies a hospital/owner.
SourceSystem: `id`, `organization_id`, `code` unique within organization,
`ehr_product`, optional `ehr_version`, `database_vendor`, `database_name`,
`status` (registered/active/suspended), `created_at`. Source IDs never change when
product versions change. Replacing a deployment requires explicit continuity review.
M1 implements these two models only; it exposes no registration API.

Connector configuration is hospital-local: source ID, vendor, credential reference,
TLS settings, database/schema allowlist, sample limits and extraction policy. The
central source record contains neither a password nor a usable connection URI.

## Normalized schema (M1 contract)

`DatabaseSchema`: `contract_version=1`, `source_system_id`, `database_name`,
`vendor`, `scanned_at`, `tables`. Table identity is (`namespace`, `name`), preserving
case; column identity is (table identity, column name). Catalog is `database_name`.
`namespace` can be empty only when a vendor has no schema namespace.

`TableSchema`: namespace/name, optional comment, columns, ordered primary_key,
foreign_keys, unique_constraints, indexes, relationship_hints.
`ColumnSchema`: name, ordinal, native_type, normalized_type
(string/integer/decimal/boolean/date/datetime/binary/json/uuid/unknown), nullable,
optional default/comment/precision/scale/length. Preserve unknown native types.
PK/FK/unique column lists preserve order. FK specifies the referenced namespace,
table and ordered columns; references outside the scan allowlist remain visible.
Indexes contain name, ordered columns, unique and optional expression; expression
indexes are preserved as metadata, never executed. Relationship hints identify
local/remote columns, confidence and evidence, distinct from declared FKs.

Fingerprint: SHA-256 of canonical sorted structural JSON (tables by qualified
identity; columns by ordinal; constraints/indexes by name). Exclude
scan time, samples, distributions, defaults/comments and relationship hints because
they do not define structural compatibility; hints remain in the scan record.
Include datatype/nullability/key/index changes. Compatibility is later checked
against a release's actual dependencies; a fingerprint change alone requires review,
not automatic mapping deletion. No sampling is part of this contract.

`ColumnProfile` (M1 boundary contract): schema fingerprint, qualified column, bounded
distinct values, sample_count/null_count, scope, sampling method, time and truncation
flag. Null fraction derives from counts (undefined for zero sample_count). Rich record
samples and distribution summaries are future additions. Estimates
are not asserted to describe the complete DB. Access is recorded as a business audit.

## Mapping registry (future)

`MappingProposal`: proposal ID, source ID/database, schema fingerprint, resource
assembly ID, mapping version, source field references (native type, join path,
record keys), target resource/profile version, target element path, mapping type,
transformation AST/version, evidence, confidence, status, created_at.
Confidence has `score: number|null` in [0,1], `method`, `calibration_version:null|string`,
`reasons[]`; an uncalibrated model score is not a probability.

`ResourceAssembly`: scoped extraction root, record key and patient key, reviewed
join edges with cardinality, fields, repeating-array grouping, reference recipes and
required-field policy. A field mapping alone cannot reconstruct FHIR resources.
Target paths use actual R4 element names (`name[].family`, `identifier[].value`,
`valueQuantity.value`); array group IDs bind fields to the same repeated object.
Reject invalid choice elements, ambiguous joins and uncontrolled SQL expressions.

`MappingRelease`: immutable source/database release version, schema dependencies,
approved assembly/mapping versions, FHIR package versions, interpreter version,
digest, creator/reviewer/time. Runtime consumes the complete validated release,
never a mutable collection of latest proposals. Approval applies to an exact digest.
Edits create a new version in proposed state and invalidate old approval for that edit.

Review states: proposed -> needs_review/approved/rejected/unresolved;
needs_review/unresolved -> proposed after correction; approved -> deprecated;
rejected -> new proposed version after correction. Rejections and review history
are retained. An approved mapping is immutable; deprecation stops new release use.
Historical ingestions retain its version. No score threshold silently approves.

## Identity (future)

GlobalPatient is an internal identity container, not a replacement hospital Patient.
SourcePatient is unique (`source_system_id`, `source_patient_id`), preserves source
identifiers and demographic versions. IdentityLink binds it to a global patient,
with evidence/policy version, creator/time and valid interval. Only one active link
per source patient. Unlink/relink closes the previous interval with review/audit;
never deletes history or rewrites original hospital identities.

IdentityCase stores input digest, source patient version, bounded candidates,
scores/conflicts, policy version, outcome and optional review. Outcome:
existing_link / linked / new_patient / needs_review. Pending cases keep clinical
resources under source identity; they are absent from a claimed global history until
resolved. Human approval is an explicit command, not a freeform model field.

## Clinical and provenance (future)

SourceResourceVersion: source/database/table record key, resource type/logical ID,
source revision, patient source key (nullable for non-patient resources), original
FHIR payload, content digest, mapping release/version, transformation version,
source effective time, ingested_at and validation result.

Resource IDs are source-namespaced, deterministic and collision-checked; no raw
identifier needs to be publicly exposed. Global query associations are through active
identity links. FHIR reference resolution uses a source key map, not names.

IngestionBatch/outbox records and append-only AuditEvent tie all operations to
authenticated actors, correlation IDs and stable digests. FHIR Provenance supplements
internal metadata; exact source payload and original source keys are retained under
access controls, even when the longitudinal projection normalizes references.
