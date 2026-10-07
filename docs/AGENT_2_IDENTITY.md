# Agent 2: central identity and orchestration

Design contract v1; implementation begins at M7. Identity linking changes a query
association, not the source Patient or clinical payload.

## Inputs and outputs

IdentityResolutionInput: `{contract_version:1, case_id:UUID,
source_system_id:UUID, source_patient_id:string, patient_resource_version_id:UUID,
patient:PatientR4, provenance_ref:UUID, policy_version:string}`. Patient is an
already validated, source-namespaced resource. Host loads bounded authorized
candidate evidence; caller cannot inject an arbitrary global target to link.

IdentityResolutionOutput: `{case_id:UUID, outcome:
existing_link|linked|new_patient|needs_review, global_patient_id:UUID|null,
identity_link_id:UUID|null, candidates:[{global_patient_id:UUID,
score:number|null,method:string,calibration_version:string|null,
evidence:Evidence[],conflicts:Evidence[]}],
policy_version:string,review_case_id:UUID|null,decision_reason:string}`.
For needs_review both global/link IDs are null. Persisted link output includes
actor/time/decision ID. Outcome new_patient atomically creates container plus source
link; it does not assert national identifier allocation or uniqueness of a person.

Evidence: `{type:string,issuer:string|null,field:string,comparison:string,
reliability:string,source_version_ref:UUID,details_ref:UUID|null}`. Raw sensitive
comparison values are accessible only through the protected case, not API logs.
Probabilistic score carries calibration version; uncalibrated scores are ranking only.

## Decision order and risk

1. Look up active (source, patient key) link. This is the primary future lookup.
   Material conflicting verified identifiers hold new association and open review;
   never automatically relink an existing identity.
2. Compare issuer-qualified, verified exact identifiers. NID, BRN and UHID/Health ID
   are distinct namespaces; string equality without issuer or verification is weak.
   Multiple hits, conflicting authoritative identifiers or incompatible demographics
   force review, not first-row matching.
3. Normalize with versioned Unicode/whitespace/name/phone/address rules preserving
   original values, Bangla spellings, locale and partial birth dates. Missing != match.
4. Deterministic blocking reduces candidates; DOB/name alone never authorizes link.
   Add weighted fuzzy evidence only after controlled calibration. Changed phone,
   shared family phone and abbreviated names are common ambiguity, not unique IDs.
5. Difficult cases may receive bounded rich-record reasoning via provider abstraction.
   Model result `{candidate_id,recommendation,evidence_refs,uncertainties}` is advisory,
   JSON-validated, evidence-grounded and cannot create/update an IdentityLink.
6. Initial policy requires human approval for every cross-source candidate link.
   No automatic fuzzy or model-based linkage. Creating a provisional separate global
   patient when no plausible candidate exists is allowed; uncertain cases remain
   needs_review with source-only resources. Later verified exact automatic linkage
   requires explicit ADR, conflict checks, calibration and audited risk policy.
7. Reviewer selects an existing candidate or creates a new identity with revision and
   reason. Store decision/link/audit atomically and enforce one active link/source key.

Do not blend inconsistent demographics into a made-up golden patient. Query reports
source versions and discrepancies. Reviewer unlink/relink closes an interval and
creates a new decision; history remains and projections rebuild from active links.

## Required evaluation

Measure false-positive links separately from recall/review load. Hold out adversarial
same-name/DOB different-person cases, missing NID, incorrect NID, changed/shared
phone, abbreviation, transliteration, address inconsistency and contradictory DOB.
Test replay, duplicate pending cases, concurrent links, link conflict, stale review,
unlink and the no-model stored-link path. False-positive links carry greater harm
than duplicates; no performance target may relax this invariant silently.
