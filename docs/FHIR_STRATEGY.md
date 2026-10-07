# FHIR strategy

Canonical target: HL7 FHIR R4 **4.0.1**, not R4B/R5. Initial package evaluation:
`hl7.fhir.r4.core#4.0.1` and `bd.fhir.core#0.4.6`. The latter is a Phase 0 candidate
pin; package availability/checksum, dependencies and patient profile compatibility
must be verified at M4 before catalog or validator use. BD-Core conformance is a goal,
not a current claim.

[DGHS BD-Core guide](https://fhir.dghs.gov.bd/core/) currently identifies version
0.4.6, informative maturity level 1, based on R4 4.0.1. Do not invent national
identifier systems or profiles. Review actual StructureDefinitions and terminology
with clinical/integration owners before selecting applicable profiles. Preserve
package versions per release/validation result; never silently refresh moving guides.

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
