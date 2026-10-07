# ADR-018: Core FHIR catalog for the demo

Accepted 2026-10-07 at the user's explicit request. The OpenMRS/OpenEMR demo
targets the global HL7 FHIR R4 core package `hl7.fhir.r4.core#4.0.1` for mapping
proposal contracts. BD-Core is outside demo scope; this supersedes ADR-002's
requirement to evaluate BD-Core before M4. A future Bangladesh deployment requires
a separate profile decision and verified package dependencies.

M4 must verify and cache the exact core package, checksum and dependencies before
deriving catalog candidates. Proposals reference its actual StructureDefinitions,
element paths, types, cardinalities and bindings. The source EHR products do not
establish FHIR conformance; transformed resources still require validation. This
decision changes documentation only; catalog implementation and Agent 1 remain
deferred.

ADR-019 subsequently authorizes and implements the M4 catalog/proposal pipeline.
