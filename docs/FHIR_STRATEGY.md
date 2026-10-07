# FHIR strategy

Canonical target: HL7 FHIR R4 **4.0.1**. The chosen demo mapping catalog is
`hl7.fhir.r4.core#4.0.1`, using official core StructureDefinitions and terminology
bindings. M4 verifies/caches the official artifact by manifest, size and pinned
SHA-256; its manifest declares no dependencies. The catalog is implemented under
ADR-019. Full FHIR resource-instance validation remains M6.

The OpenMRS/OpenEMR demo uses global core FHIR. BD-Core is outside demo scope under
[ADR-018](adr/0018-core-fhir-demo-catalog.md), superseding ADR-002's pre-M4 evaluation
requirement. A future Bangladesh deployment needs a separate decision on applicable
profiles, verified packages and national identifier semantics. Preserve package
versions per release/validation result; never silently refresh moving guides.
Source EHR product selection does not establish FHIR conformance.

The same core target catalog applies to both source systems; mappings and assemblies
remain scoped to each source deployment/database. Candidate metadata and validation
use the verified core definitions. References to profiles in future contracts mean
definitions allowed by this catalog; adding an implementation guide requires a new
accepted scope decision. Pin any verified dependencies alongside the core package.

Initial slice: Patient, Organization, Encounter, Observation and Provenance, then
Condition, Medication/MedicationRequest and related resources as source data requires.
Practitioner, Location, DiagnosticReport, Procedure, AllergyIntolerance and RelatedPerson
are anticipated, not an exhaustive model or committed first-demo scope.

Targets are nested typed element trees, not flattened resource tables. Resource
assembly must address identifiers with system/value, HumanName arrays, choice types,
references, cardinalities, terminology and profiles. FHIR element paths and repeated
group IDs are mapping metadata, not claims of arbitrary FHIRPath write support.

Validation stages: parse JSON and resource type; verify base structure/cardinality/
types/invariants; apply selected profiles/slicing; check terminology; verify source
ownership, patient references and application business rules. Use official HL7
validator adapter with pinned packages and bounded execution, capture OperationOutcome.
Pydantic JSON contracts alone are not full FHIR validation. See
[HL7 R4 validation](https://hl7.org/fhir/R4/validation.html).

Invalid historical data enters protected quarantine for remediation. Never fabricate
required values just to satisfy a profile. Never send patient data to a public
sandbox/terminology service by default; use local validation and explicitly
configured terminology access with data-flow review.

Each clinical version retains source hospital/EHR/database/patient/record/revision,
ingested_at, mapping version/release digest, interpreter version and source effective
time when known. Generate FHIR Provenance with target version reference, recorded,
agent identifying source organization/system and entity referencing the source record
using an identifier. Extensions or meta tags must have documented semantics; do not
put arbitrary fields in resources. Source identifiers remain access-controlled.

Storage initially keeps immutable JSONB source versions and reference indexes under
an application API. No FHIR CapabilityStatement or standard REST search compliance is
claimed. HAPI JPA evaluation occurs only when those capabilities are required; retain
central identity/provenance responsibilities and reconcile external storage by outbox.
