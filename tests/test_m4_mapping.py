"""M4 host contracts, catalog semantics, registry history and bounded proposal behavior."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from datapulse.contracts.schema import (
    ColumnSchema,
    DatabaseSchema,
    ForeignKeySchema,
    TableRef,
    TableSchema,
)
from datapulse.hospital.registry import HospitalRegistry, RegistryError, migrate_registry
from datapulse.mapping.__main__ import main
from datapulse.mapping.catalog import CatalogError, FHIRCatalog, verify_package
from datapulse.mapping.contracts import (
    MappingRunInput,
    MappingScope,
    MappingTask,
    MappingTaskOutput,
    task_output_schema,
)
from datapulse.mapping.discovery import classify, declared_graph
from datapulse.mapping.pipeline import MappingPipeline, RunRejected, proposal_reuse_key
from datapulse.mapping.provider import LocalModelConfig, ProviderFailure
from datapulse.mapping.validation import OutputRejected, validate_output


def catalog():
    def sd(kind, elements, category="complex-type"):
        return {
            "url": f"http://hl7.org/fhir/StructureDefinition/{kind}",
            "kind": category,
            "snapshot": {"element": [{"path": kind}, *elements]},
        }

    def element(path, datatype, maximum="1", **extra):
        return {
            "path": path,
            "type": [{"code": datatype}],
            "min": 0,
            "max": maximum,
            "short": path,
            **extra,
        }

    definitions = {
        "Patient": sd(
            "Patient",
            [
                element("Patient.birthDate", "date"),
                element(
                    "Patient.gender",
                    "code",
                    binding={
                        "strength": "required",
                        "valueSet": "http://hl7.org/fhir/ValueSet/administrative-gender|4.0.1",
                    },
                ),
                element("Patient.name", "HumanName", "*"),
            ],
            "resource",
        ),
        "HumanName": sd(
            "HumanName",
            [element("HumanName.family", "string"), element("HumanName.text", "string")],
        ),
        "Observation": sd("Observation", [element("Observation.value[x]", "Quantity")], "resource"),
        "Quantity": sd("Quantity", [element("Quantity.value", "decimal")]),
        "Encounter": sd("Encounter", [], "resource"),
        "Organization": sd("Organization", [], "resource"),
        "Provenance": sd("Provenance", [], "resource"),
        **{t: {"kind": "primitive-type"} for t in ("date", "code", "string", "decimal")},
    }
    terminology = {
        "http://hl7.org/fhir/ValueSet/administrative-gender": {
            "version": "4.0.1",
            "resourceType": "ValueSet",
            "compose": {
                "include": [
                    {
                        "system": "http://hl7.org/fhir/administrative-gender",
                        "concept": [{"code": c} for c in ("male", "female", "other", "unknown")],
                    }
                ]
            },
        }
    }
    return FHIRCatalog(definitions, "a" * 64, terminology)


def schema(name="birthdate", normalized="date", native="date", **column_changes):
    return DatabaseSchema(
        source_system_id=uuid4(),
        database_name="fixture",
        vendor="mariadb",
        scanned_at=datetime.now(UTC),
        tables=(
            TableSchema(
                namespace="fixture",
                name="patient",
                columns=(
                    ColumnSchema(
                        name=name,
                        ordinal=0,
                        native_type=native,
                        normalized_type=normalized,
                        nullable=True,
                        **column_changes,
                    ),
                ),
            ),
        ),
    )


def task_for(scan, target="birthDate"):
    c = catalog()
    candidate = next(c for c in c.candidates("Patient") if c.element_path == target)
    task_id = uuid4()
    task = MappingTask(
        task_id=task_id,
        source_system_id=scan.source_system_id,
        database_name=scan.database_name,
        schema_fingerprint=scan.structural_fingerprint(),
        tables=scan.tables,
        candidates=(candidate,),
        output_schema=task_output_schema(task_id, scan.tables, (candidate,)),
    )
    return c, task


def valid_output(task):
    ref = {
        "table": {"namespace": task.tables[0].namespace, "name": task.tables[0].name},
        "column": task.tables[0].columns[0].name,
    }
    return {
        "task_id": str(task.task_id),
        "proposals": [
            {
                "source_refs": [ref],
                "candidate_id": task.candidates[0].id,
                "target_path": task.candidates[0].element_path,
                "group_id": None,
                "mapping_type": "direct",
                "transformation": {"op": "copy", "source": ref},
                "confidence": {
                    "score": None,
                    "method": "uncalibrated",
                    "calibration_version": None,
                    "reasons": ["Native type and name"],
                },
                "evidence_refs": [str(task.task_id)],
                "rationale": "Metadata suggests this candidate",
            }
        ],
        "unresolved": [],
    }


def test_nested_datatype_choice_and_bounded_type_filtered_retrieval():
    c = catalog()
    assert "name[].family" in {v.element_path for v in c.candidates("Patient")}
    assert "valueQuantity.value" in {v.element_path for v in c.candidates("Observation")}
    assert c.retrieve("dob", "date", ("Patient",))[0].element_path == "birthDate"
    assert c.retrieve("unknown_column", "binary", ("Patient",)) == ()
    with pytest.raises(CatalogError):
        c.retrieve("dob", "date", limit=13)
    with pytest.raises(CatalogError):
        c.candidates("InventedResource")


def test_package_tampering_never_accepted(tmp_path):
    bad = tmp_path / "package.tgz"
    bad.write_bytes(b"not the pinned archive")
    with pytest.raises(CatalogError, match="checksum"):
        verify_package(bad)


def test_cli_package_failure_and_invalid_arguments_are_useful_and_redacted(tmp_path, capsys):
    cached = tmp_path / "hl7.fhir.r4.core-4.0.1.tgz"
    cached.write_bytes(b"corrupt")
    assert main(["catalog", "--cache", str(tmp_path)]) == 1
    assert "package_checksum_mismatch" in capsys.readouterr().out
    secret = "private-value-never-echo"
    assert main(["catalog", "--unknown", secret]) == 1
    output = capsys.readouterr()
    assert secret not in output.out + output.err


def test_host_validation_accepts_exact_supported_proposal():
    c, task = task_for(schema())
    output = MappingTaskOutput.model_validate(valid_output(task))
    assert validate_output(task, output, c) == output


@pytest.mark.parametrize("change", ["task", "candidate", "path", "source", "evidence", "missing"])
def test_host_rejects_forged_or_incomplete_output(change):
    c, task = task_for(schema())
    payload = valid_output(task)
    field = payload["proposals"][0]
    if change == "task":
        payload["task_id"] = str(uuid4())
    if change == "candidate":
        field["candidate_id"] = "forged"
    if change == "path":
        field["target_path"] = "birthDate.sql"
    if change == "source":
        field["source_refs"][0]["column"] = "absent"
    if change == "evidence":
        field["evidence_refs"] = [str(uuid4())]
    if change == "missing":
        payload["proposals"] = []
    with pytest.raises(OutputRejected):
        validate_output(task, MappingTaskOutput.model_validate(payload), c)


@pytest.mark.parametrize(
    "transformation",
    [
        {"op": "eval", "code": "SELECT password FROM users"},
        {
            "op": "copy",
            "source": {"table": {"namespace": "fixture", "name": "patient"}, "column": "birthdate"},
            "sql": "SELECT 1",
        },
    ],
)
def test_arbitrary_sql_code_and_extra_fields_rejected(transformation):
    _, task = task_for(schema())
    payload = valid_output(task)
    payload["proposals"][0]["transformation"] = transformation
    with pytest.raises(ValidationError):
        MappingTaskOutput.model_validate(payload)


def test_invalid_type_repeated_group_and_required_terminology():
    c, task = task_for(schema(normalized="integer", native="int"))
    with pytest.raises(OutputRejected, match="type_mismatch"):
        validate_output(task, MappingTaskOutput.model_validate(valid_output(task)), c)
    c, task = task_for(schema("family_name", "string", "varchar(100)"), "name[].family")
    with pytest.raises(OutputRejected, match="array_group_required"):
        validate_output(task, MappingTaskOutput.model_validate(valid_output(task)), c)
    c, task = task_for(schema("gender", "string", "varchar(20)"), "gender")
    with pytest.raises(OutputRejected, match="terminology_source_evidence_required"):
        validate_output(task, MappingTaskOutput.model_validate(valid_output(task)), c)
    payload = valid_output(task)
    field = payload["proposals"][0]
    field["mapping_type"] = "transformed"
    field["transformation"] = {
        "op": "code_map",
        "source": field["source_refs"][0],
        "values": {"M": "male", "F": "female"},
        "on_unmapped": "quarantine",
    }
    validate_output(task, MappingTaskOutput.model_validate(payload), c)
    field["transformation"]["values"]["U"] = "not-a-gender"
    with pytest.raises(OutputRejected, match="terminology_unverified"):
        validate_output(task, MappingTaskOutput.model_validate(payload), c)


def test_immutable_registry_deduplicates_structure_preserves_observations_and_source(tmp_path):
    path = tmp_path / "registry.sqlite"
    with pytest.raises(RegistryError):
        HospitalRegistry(path)
    migrate_registry(path)
    registry = HospitalRegistry(path)
    first = schema(comment="first", default="NULL")
    second = first.model_copy(
        update={
            "scanned_at": datetime.now(UTC),
            "tables": (
                first.tables[0].model_copy(
                    update={
                        "columns": (
                            first.tables[0]
                            .columns[0]
                            .model_copy(update={"comment": "second", "default": "1"}),
                        )
                    }
                ),
            ),
        }
    )
    a, b = registry.save_scan(first), registry.save_scan(second)
    assert a.scan_id != b.scan_id and a.schema_fingerprint == b.schema_fingerprint
    registry.close()
    registry = HospitalRegistry(path)
    assert registry.load_scan(a.scan_id, first.source_system_id) == first
    assert registry.load_scan(b.scan_id, first.source_system_id) == second
    with pytest.raises(RegistryError):
        registry.load_scan(a.scan_id, uuid4())
    changed = second.model_copy(
        update={
            "tables": (
                second.tables[0].model_copy(
                    update={
                        "columns": (
                            second.tables[0].columns[0].model_copy(update={"nullable": False}),
                        )
                    }
                ),
            )
        }
    )
    assert registry.save_scan(changed).schema_fingerprint != b.schema_fingerprint
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM schema_snapshots").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM schema_scans").fetchone()[0] == 3
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM schema_scans")
    registry.close()


def request_for(scan):
    return MappingRunInput(
        run_id=uuid4(),
        source_system_id=scan.source_system_id,
        database_name=scan.database_name,
        schema_fingerprint=scan.structural_fingerprint(),
        schema_scan_id=uuid4(),
        scope=MappingScope(tables=(TableRef(namespace="fixture", name="patient"),)),
    )


class FakeProvider:
    def __init__(self, mode="valid"):
        self.mode, self.calls, self.corrections = mode, 0, []

    def generate(self, task, correction_code=None):
        self.calls += 1
        self.corrections.append(correction_code)
        if self.mode == "timeout":
            raise ProviderFailure("timeout")
        payload = valid_output(task)
        if self.mode == "invalid":
            payload["proposals"][0]["candidate_id"] = "forged"
        if self.mode == "correct" and self.calls == 1:
            payload["proposals"][0]["candidate_id"] = "forged"
        return MappingTaskOutput.model_validate(payload)

    def metadata(self):
        return {"provider": "test"}


@pytest.mark.parametrize(
    "mode,calls,status",
    [
        ("valid", 1, "completed"),
        ("correct", 2, "completed"),
        ("invalid", 3, "failed"),
        ("timeout", 1, "failed"),
    ],
)
def test_pipeline_bounded_correction_and_proposed_only_persistence(tmp_path, mode, calls, status):
    scan = schema()
    provider = FakeProvider(mode)
    result = MappingPipeline(catalog(), provider).run(request_for(scan), scan)
    assert provider.calls == calls and result.status == status
    assert all(p.status == "proposed" for p in result.proposals)
    assert bool(result.unresolved_fields) == (status == "failed")
    path = tmp_path / "registry.sqlite"
    migrate_registry(path)
    registry = HospitalRegistry(path)
    receipt = registry.save_scan(scan)
    assert registry.save_run(receipt.scan_id, scan.source_system_id, result) == result.run_id
    registry.close()


def test_unknown_field_stays_unresolved_and_source_mismatch_rejected():
    scan = schema("opaque", "unknown", "future_type")
    provider = FakeProvider()
    result = MappingPipeline(catalog(), provider).run(request_for(scan), scan)
    assert result.unresolved_fields and provider.calls == 0
    with pytest.raises(RunRejected):
        MappingPipeline(catalog(), provider).run(request_for(schema()), scan)
    assert classify(scan.tables[0]).resources == ("Patient",)
    assert declared_graph(scan) == ()


@pytest.mark.parametrize("extra", [{"credentials": "secret"}, {"sql": "SELECT * FROM patient"}])
def test_mapping_task_never_accepts_credential_or_sql_fields(extra):
    _, task = task_for(schema())
    with pytest.raises(ValidationError):
        MappingTask.model_validate({**task.model_dump(), **extra})


@pytest.mark.parametrize(
    "changes",
    [
        {"endpoint": "http://remote.example:11434"},
        {"endpoint": "http://localhost:11434"},
        {"endpoint": "http://127.0.0.1:11434/leak"},
        {"model": "anything:latest"},
        {"model_digest": "unknown"},
    ],
)
def test_provider_requires_explicit_local_runtime_and_artifact(changes):
    with pytest.raises(ValidationError):
        LocalModelConfig.model_validate(
            {"model": "fixture:1b", "model_digest": "a" * 64, "runtime_version": "1.0", **changes}
        )


def test_contract_bounds_and_core_target():
    scan = schema()
    payload = request_for(scan).model_dump(mode="json")
    payload["target"]["packages"] = [{"id": "bd.fhir.core", "version": "0.4.6"}]
    with pytest.raises(ValidationError):
        MappingRunInput.model_validate(payload)
    _, task = task_for(scan)
    with pytest.raises(ValidationError):
        MappingTask.model_validate({**task.model_dump(), "output_schema": {}})
    columns = tuple(
        scan.tables[0].columns[0].model_copy(update={"name": f"c{i}", "ordinal": i})
        for i in range(41)
    )
    with pytest.raises(ValidationError):
        MappingTask.model_validate(
            {
                **task.model_dump(),
                "tables": [
                    scan.tables[0].model_copy(update={"columns": columns}),
                ],
            }
        )


def test_proposal_reuse_tracks_source_catalog_model_and_semantic_input(tmp_path):
    scan = schema()
    request = request_for(scan)
    provider = FakeProvider()
    c = catalog()
    key = proposal_reuse_key(request, scan, None, c, provider)
    repeated = scan.model_copy(update={"scanned_at": datetime.now(UTC)})
    assert proposal_reuse_key(request, repeated, None, c, provider) == key
    changed_catalog = FHIRCatalog(c._definitions, "b" * 64)
    assert proposal_reuse_key(request, repeated, None, changed_catalog, provider) != key
    changed = scan.model_copy(
        update={"tables": (scan.tables[0].model_copy(update={"comment": "new meaning"}),)}
    )
    assert changed.structural_fingerprint() == scan.structural_fingerprint()
    assert proposal_reuse_key(request, changed, None, c, provider) != key
    path = tmp_path / "registry.sqlite"
    migrate_registry(path)
    registry = HospitalRegistry(path)
    receipt = registry.save_scan(scan)
    result = MappingPipeline(c, provider).run(request, scan)
    registry.save_run(receipt.scan_id, scan.source_system_id, result)
    assert registry.find_run(scan.source_system_id, key)["run_id"] == str(result.run_id)
    assert registry.find_run(uuid4(), key) is None
    registry.close()


def test_hospital_migration_upgrade_downgrade_and_revision_guard(tmp_path):
    path = tmp_path / "registry.sqlite"
    migrate_registry(path)
    engine = sa.create_engine(sa.URL.create("sqlite", database=str(path)))
    import datapulse.hospital.registry as module

    config = Config()
    config.set_main_option("script_location", str(Path(module.__file__).parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "hospital_0001")
    with pytest.raises(RegistryError, match="revision_mismatch"):
        HospitalRegistry(path)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert not set(sa.inspect(connection).get_table_names()) & {
            "schema_snapshots",
            "schema_scans",
            "mapping_runs",
        }
    engine.dispose()
    migrate_registry(path)
    HospitalRegistry(path).close()


def test_inherited_codeable_concept_binding_is_not_lost():
    c = catalog()
    c._definitions["Patient"]["snapshot"]["element"].append(
        {
            "path": "Patient.maritalStatus",
            "min": 0,
            "max": "1",
            "type": [{"code": "CodeableConcept"}],
            "binding": {"strength": "required", "valueSet": "fixture-codes"},
        }
    )
    c._definitions["CodeableConcept"] = {
        "kind": "complex-type",
        "snapshot": {
            "element": [
                {"path": "CodeableConcept"},
                {
                    "path": "CodeableConcept.coding",
                    "min": 0,
                    "max": "*",
                    "type": [{"code": "Coding"}],
                },
            ]
        },
    }
    c._definitions["Coding"] = {
        "kind": "complex-type",
        "snapshot": {
            "element": [
                {"path": "Coding"},
                {"path": "Coding.code", "min": 0, "max": "1", "type": [{"code": "code"}]},
                {"path": "Coding.display", "min": 0, "max": "1", "type": [{"code": "string"}]},
            ]
        },
    }
    candidates = {v.element_path: v for v in c.candidates("Patient")}
    assert candidates["maritalStatus.coding[].code"].binding["strength"] == "required"
    assert candidates["maritalStatus.coding[].display"].binding is None


def test_reference_recipe_requires_declared_key_and_allowed_target_profile():
    c = catalog()
    c._definitions["Patient"]["snapshot"]["element"].append(
        {
            "path": "Patient.managingOrganization",
            "min": 0,
            "max": "1",
            "type": [
                {
                    "code": "Reference",
                    "targetProfile": [
                        "http://hl7.org/fhir/StructureDefinition/Organization",
                    ],
                }
            ],
        }
    )
    scan = schema("organization_id", "integer", "int")
    table = scan.tables[0].model_copy(
        update={
            "foreign_keys": (
                ForeignKeySchema(
                    name="fk_org",
                    columns=("organization_id",),
                    referenced_table=TableRef(namespace="fixture", name="organizations"),
                    referenced_columns=("id",),
                ),
            )
        }
    )
    target = next(v for v in c.candidates("Patient") if v.element_path == "managingOrganization")
    task_id = uuid4()
    task = MappingTask(
        task_id=task_id,
        source_system_id=scan.source_system_id,
        database_name="fixture",
        schema_fingerprint=scan.structural_fingerprint(),
        tables=(table,),
        candidates=(target,),
        output_schema=task_output_schema(task_id, (table,), (target,)),
    )
    payload = valid_output(task)
    field = payload["proposals"][0]
    field["mapping_type"] = "reference"
    field["transformation"] = {
        "op": "reference",
        "source": field["source_refs"][0],
        "target_resource": "Organization",
        "on_missing": "quarantine",
    }
    validate_output(task, MappingTaskOutput.model_validate(payload), c)
    field["transformation"]["target_resource"] = "Patient"
    with pytest.raises(OutputRejected, match="reference_target_mismatch"):
        validate_output(task, MappingTaskOutput.model_validate(payload), c)
