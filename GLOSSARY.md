# DataPulse

DataPulse connects information from separately owned hospital record systems while
preserving original identities and the origin of every record.

## Language

**Hospital (Organization)**:
The hospital or owner responsible for one or more source systems.

**Source system**:
A particular hospital record-system deployment and database, with its own stable
identity. Two installations of the same product are different source systems.
_Avoid_: Vendor mapping, universal connector

**Registration**:
The saved description of a hospital or source system. Registration does not mean
its database is connected or its records have been inspected.
_Avoid_: Verified connection

**Connector identity**:
The identity authorized to act for exactly one registered source system.

**Connector access key**:
A credential proving a connector identity to DataPulse. It is separate from the
credentials used to access a hospital database.
_Avoid_: Hospital password

**Retirement**:
The withdrawal of a registration and its connector access while retaining its
identity and activity history.
_Avoid_: Erasing history

**Preview**:
A fictional demonstration workflow whose review decisions do not affect saved
registrations or actual patient records.

**FHIR target catalog**:
The agreed collection of FHIR resource and element definitions that hospital
information may be mapped to. Source-specific mappings share this target vocabulary.
_Avoid_: Hospital schema catalog

**Schema scan**:
An observation of a source database's structure at a particular time. It describes
tables, fields and declared relationships, rather than patient records.

**Schema fingerprint**:
The identity of an observed structural shape within a source system. Observations
can share the same structural shape while retaining different descriptive evidence.

**Mapping proposal**:
A suggested interpretation of source information in the agreed FHIR vocabulary.
It requires review before becoming an approved mapping.
_Avoid_: Approved mapping, executable mapping

**Relationship evidence**:
Observed support or contradictions for a proposed relationship between source records.
Matching values alone do not establish that records belong together.

**Clinical coverage**:
The clinical information a reviewed mapping release accounts for, together with visible
unresolved work. A Patient-only release does not cover an entire medical record.
