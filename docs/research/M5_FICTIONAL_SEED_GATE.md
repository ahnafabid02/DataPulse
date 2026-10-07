# Fictional clinical seed compatibility gate

Reviewed 2026-10-08. This research supports the authorized profiling and relationship
evidence slice before M5 review/releases. It does not implement approval, clinical
transformation or ingestion. The fixture is a disposable database test corpus, not
an upstream certified patient creation workflow or a complete clinical export.

## Pinned baseline and research evidence

Retain every image and database pin in `infra/demo/images.lock.json` and
`infra/demo/compose.yaml`: OpenMRS Reference Application 3.7.1/core 2.8.8 on
MariaDB 10.11.7; OpenEMR 8.4.1/schema 543 on MariaDB 12.3.3. The existing M3 notes
record image digests and application installation acceptance. No new image, module,
terminology import or floating dependency is needed for the small fixture.

Research inspected the locally persisted M4 metadata scans, pinned upstream source,
and read-only support metadata in the running disposable sources. On this host,
OpenMRS has users 1 and 2, Numeric datatype 1 (`NM`), Text datatype 3 (`ST`),
N/A datatype 4 (`ZZ`), Test concept class 1, Finding class 5 and Question class 7.
OpenEMR has facility 3 and users 1 through 4. Both patient tables were empty when
checked. These are observed prerequisites, not universal IDs: the fixture operator
must verify them again and fail if its expected identities or metadata change.

## Recommended import boundary

Use reviewed, deterministic, demo-only SQL against existing upstream clinical
tables, executed by the separate infrastructure bootstrap operator. The DataPulse
connector remains SELECT-only. Model output never supplies executable SQL. Restrict
the operator to the named `datapulse-m3-demo` project, exact source/database/image
pins, and an empty or exactly recognized fixture baseline. Verify fixture ownership
before replacing rows; refuse any unexpected patient/encounter/observation data.

This choice is an engineering inference for reproducibility. Application creation
services deliberately allocate IDs and UUIDs, derive current timestamps, dispatch
events and perform validation. Bypassing those services therefore cannot claim
equivalent application invariants, ACL checks or audit events. OpenEMR's
[PatientService](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/src/Services/PatientService.php)
allocates `pid`, sets creation/update dates and authenticated creator information,
and creates a UUID. Its
[EncounterService](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/src/Services/EncounterService.php)
allocates an encounter number and UUID and adds a corresponding form row. An API
seed would require additional application authentication and generated-ID receipt
handling, and cannot create the deliberate orphan fixture through normal validation.

Keep source-specific fixture logic exclusively in `infra/demo`; generic connector
profiling and relationship contracts must not branch on an EHR product name.
Store all seed values as explicitly fictional constants, fixed UTC-naive source
dates, positive reserved numeric keys, and deterministic UUIDs. Preserve the
unmodified upstream schema: no new clinical tables and no added synthetic FKs.
Do not disable OpenMRS foreign-key checks to manufacture invalid rows.

## OpenMRS insertion requirements

The installed schema and the pinned
[Patient Hibernate mapping](https://github.com/openmrs/openmrs-core/blob/2.8.8/api/src/main/resources/org/openmrs/api/db/hibernate/Patient.hbm.xml)
agree that `patient` extends `person` using the same numeric key. A patient must
have its `person` row first. Names and identifiers are separate repeated records.

For the initial corpus, explicitly provide these columns rather than relying on
zero-valued FK defaults:

- `person`: `person_id`, `gender`, nullable `birthdate`, `birthdate_estimated`,
  `dead`, `creator`, `date_created`, `voided`, `uuid`.
- `patient`: `patient_id` equal to `person.person_id`, `creator`, `date_created`,
  `voided`. There is no separate patient UUID column; UUID belongs to `person`.
- `person_name`: `person_name_id`, `person_id`, `preferred`, `given_name`, nullable
  `middle_name`, `family_name`, `creator`, `date_created`, `voided`, `uuid`.
- `patient_identifier`: `patient_identifier_id`, `patient_id`, `identifier`,
  `identifier_type`, `preferred`, `location_id`, `creator`, `date_created`,
  `voided`, `uuid`. Set location to the fixture's real location or explicitly
  NULL; its installed default 0 is not evidence that location 0 exists.

Create owned support rows before identifiers/encounters/observations:

- `patient_identifier_type`: `patient_identifier_type_id`, unique fixture name,
  `creator`, `date_created`, `uuid`, `required`, `check_digit` and explicit
  `uniqueness_behavior`. Keep actual patient identifiers unique; duplicate-looking
  strings are distinct test cases, not an invitation to bypass identifier validation.
- `location`: `location_id`, fixture name, `creator`, `date_created`, `uuid`.
- `encounter_type`: `encounter_type_id`, unique fixture name, `creator`,
  `date_created`, `uuid`.
- `concept`: `concept_id`, explicit existing `datatype_id` and `class_id`,
  `creator`, `date_created`, `uuid`, `is_set=0`, `retired=0`.
- `concept_name`: `concept_name_id`, `concept_id`, fictional display name,
  `locale='en'`, `locale_preferred=1`, `concept_name_type='FULLY_SPECIFIED'`,
  `creator`, `date_created`, `uuid`.
- For numeric concepts, `concept_numeric`: `concept_id`, explicit `units` and
  `allow_decimal`; keep units source-local until a reviewed terminology mapping.

`encounter` requires explicit ID, patient, type, datetime, creator, creation date
and UUID; optional location can use the owned fixture row. `obs` requires explicit
ID, person, concept, observation datetime, creator, creation date and UUID, plus
the appropriate typed value and optional encounter/location. Preserve `status='FINAL'`
and voiding flags. Numeric concepts use numeric values; missing demographics can
exercise null handling without creating observations with no clinical value.
The pinned [Obs mapping](https://github.com/openmrs/openmrs-core/blob/2.8.8/api/src/main/resources/org/openmrs/api/db/hibernate/Obs.hbm.xml)
requires person, concept and creator and separates numeric, coded, text and datetime
values. [ConceptNumeric](https://github.com/openmrs/openmrs-core/blob/2.8.8/api/src/main/java/org/openmrs/ConceptNumeric.java)
holds the units and numeric interpretation metadata.

Suggested order: support metadata -> person -> patient -> names/identifiers ->
encounters -> observations. Remove only recognized fixture rows in reverse order.
Verify declared FKs still enforce person/patient/encounter/observation relationships.

## OpenEMR insertion requirements

The [pinned schema 543](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/sql/database.sql)
and installed M4 scan show no declared FKs. `patient_data.pid` is unique and is
the clinical patient identity; row `id` is a separate key. `uuid` uses binary(16).
Provide explicit `id`, `pid`, binary UUID, `pubpid`, names, nullable DOB, sex,
registration/update timestamps and creator/updater fields. Empty strings represent
missing values in several NOT NULL text fields; do not insert NULL there.

For `form_encounter`, explicitly provide distinct row `id` and clinical `encounter`
number, binary UUID, patient `pid`, dates, reason, class/category, facility and
provider information. Select existing support rows only after prerequisite checks.
One patient has multiple encounters. One intentional fixture-only orphan `pid`
may exercise unmatched-key rejection; clearly mark that row in the ownership
manifest and expected evidence, and never present it as a valid clinical record.

The pinned EncounterService explicitly joins `form_encounter.pid` to
`patient_data.pid`, not `patient_data.id`. That source-code evidence supplements
deterministic uniqueness and unmatched-value checks; it does not authorize any
DataPulse join until human review.

Create the companion `forms` record for each encounter:
`formdir='newpatient'`, `form_id=form_encounter.id`,
`encounter=form_encounter.encounter`, and matching `pid`, date, authorization,
user/group and deletion state. Vital rows live in `form_vitals`; they have a
patient key but no encounter column. Link a vital row through a `forms` record
with `formdir='vitals'` and `form_id=form_vitals.id`, then the matching encounter
number/patient. A bare join on `forms.form_id` is ambiguous across form kinds.
This companion-row behavior is confirmed by
[FormService](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/src/Services/FormService.php)
and [form helpers](https://github.com/openemr/openemr/blob/a43edad9ea6d969fcbcc1df7d8ccc50ad34fd872/library/forms.inc.php).

Explicitly set vital measurement values and timestamps; do not treat the schema's
zero defaults as proof a measurement occurred. Full vital unit interpretation and
complete resource assembly require later reviewed recipes. Suggested order:
patients -> encounters -> vitals -> companion forms; cleanup reverses it.

## Fixture cases and acceptance

Use at least three patients per source, with fixed distinguishable source IDs;
two visits for one patient; repeated names/identifiers where supported; missing
DOB or middle name; duplicate-looking public identifiers; and OpenEMR's single
clearly labelled orphan. Prefer deliberately different `patient_data.id`/`pid`
and `form_encounter.id`/`encounter` values so an incorrect join cannot pass by
accidental numeric equality. Do not equate same names across sources with identity.

Keep a versioned manifest of tables, exact owned keys, row counts, timestamps,
UUIDs and expected relationship outcomes, plus a fixture definition digest.
Apply transactionally per source, not as an assumed cross-source transaction.
Before accepting reproduction, verify counts and canonical content digest after
first apply, unchanged reapply, recognized fixture removal/reapply and a dedicated
clean-volume reinstall using the exact pinned startup procedure. Account for
background timestamp/UUID changes by specifying relevant canonical columns rather
than silently ignoring clinical values. Source schema fingerprints must remain
unchanged. Wrong versions, foreign rows, fixture-key collisions and interrupted
apply must fail safely with sanitized metadata-only diagnostics.

The full project reset is already scoped to dedicated Compose volumes. OpenEMR
DB/site/log volumes must be reset together; OpenMRS DB/backend-data volumes must
remain consistent. Hospital registry history remains source-scoped and is not
automatically deleted by source reset. Record new profiling/evidence observations
after reapply; previous observations never prove the state of a recreated database.

Research acceptance: pinned source semantics and local support prerequisites were
verified read-only. No patient data was inserted or reset by this research task.
Actual import, repeated apply, rollback, restart and clean-reset acceptance remain
implementation checks. The small fixture covers only initial Patient/Encounter/
Observation evidence paths; it does not satisfy the user's full clinical-domain
mapping coverage requirement. Remaining domains must stay visible in the coverage
inventory, including data stored outside relational tables.

## Clean-reset startup investigation

During the parent implementation's clean-volume reproduction check, OpenMRS's
installed core version and empty clinical baseline matched, but the REST session
endpoint returned HTTP 404 after the first required restart. A wider sanitized
startup log showed the initial cause before the later scheduler exceptions:
`Listener.performWebStartOfModules` could not refresh the application context
because EMR API attempted to insert an existing provider UUID. The subsequent
appointment/stock-management task class-loading failures followed module shutdown;
they do not establish a missing image artifact as the initial cause.

The distribution pins EMR API 3.4.0. Its
[createUnknownProvider startup code](https://github.com/openmrs/openmrs-module-emrapi/blob/3.4.0/api/src/main/java/org/openmrs/module/emrapi/EmrApiActivator.java)
first resolves metadata mappings and EMR/core global properties. If none resolves,
it creates an unknown provider with fixed UUID
`f9badd80-ab76-11e2-9e96-0800200c9a66`. Read-only inspection found exactly one
provider with that UUID and an existing `provider.unknownProviderUuid` property
whose value was NULL. The uniqueness failure therefore has an evidenced bootstrap
metadata inconsistency, rather than a clinical seed collision.

A proposed narrow demo bootstrap recovery is to verify the exact application/
image pins and existing unknown-provider identity, populate that existing core
property with the provider UUID, and restart the application before repeating
authenticated REST readiness and empty-baseline checks. Do not delete the provider,
disable its unique constraint or weaken readiness acceptance. Make any recovery
idempotent and reject an unexpected configured property value. This research task
performed no recovery writes or restart; parent implementation must record actual
recovery and repeat-start acceptance separately.
