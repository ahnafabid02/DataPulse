"""Real source evidence after the exact fictional seed, no test DML."""

import os
import sys
from pathlib import Path

import pytest

from datapulse.connectors.connection import ConnectionConfig, FileCredentialResolver
from datapulse.connectors.evidence import (
    EvidencePolicy,
    EvidenceRequest,
    MySQLEvidenceReader,
    ProfileSelection,
    RelationshipSelection,
)
from datapulse.connectors.introspection import MySQLSchemaScanner, ScanPolicy
from datapulse.contracts.schema import TableRef
from datapulse.hospital.registry import HospitalRegistry, migrate_registry


@pytest.mark.source_db
@pytest.mark.parametrize("source", ["openmrs", "openemr"])
def test_seeded_profiles_relationships_limits_and_persistence(source, tmp_path):
    location = os.environ.get("DATAPULSE_DEMO_TEST_DIR")
    if not location:
        pytest.skip("Set DATAPULSE_DEMO_TEST_DIR for the accepted fictional EHRs")
    local = Path(location)
    config = ConnectionConfig.model_validate_json((local / f"{source}.json").read_bytes())
    expected = {
        "openmrs": (13306, "0385fb0c-b004-4a57-9523-9e53fb9af033"),
        "openemr": (13307, "aa5874e0-0482-4621-805d-afb2ad244cd4"),
    }[source]
    assert (config.host, config.port, str(config.source_system_id), config.database) == (
        "127.0.0.1",
        *expected,
        source,
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra/demo"))
    from seed_clinical import verify_seed

    assert verify_seed(source), "Refusing clinical data outside the exact fictional fixture"
    credentials = FileCredentialResolver(local / "credentials.json")
    schema = MySQLSchemaScanner(config, credentials, ScanPolicy()).introspect(
        config.source_system_id
    )
    if source == "openmrs":
        profile = ProfileSelection(
            table=TableRef(namespace=source, name="person"), columns=("gender", "birthdate")
        )
        join = RelationshipSelection(
            source_table=TableRef(namespace=source, name="encounter"),
            source_columns=("patient_id",),
            target_table=TableRef(namespace=source, name="patient"),
            target_columns=("patient_id",),
        )
    else:
        profile = ProfileSelection(
            table=TableRef(namespace=source, name="patient_data"), columns=("sex", "DOB", "fname")
        )
        join = RelationshipSelection(
            source_table=TableRef(namespace=source, name="form_encounter"),
            source_columns=("pid",),
            target_table=TableRef(namespace=source, name="patient_data"),
            target_columns=("pid",),
        )
    request = EvidenceRequest(
        source_system_id=config.source_system_id,
        schema_fingerprint=schema.structural_fingerprint(),
        profiles=(profile,),
        relationships=(join,),
    )
    reader = MySQLEvidenceReader(config, credentials)
    observed = reader.capture(request, schema)
    assert observed.profiles[1].null_count > 0
    checked = observed.relationships[0]
    assert checked.complete and not checked.approved and checked.target_duplicate_key_groups == 0
    assert checked.source_duplicate_key_groups == 1
    assert checked.unmatched_source_rows == (1 if source == "openemr" else 0)
    assert checked.status == ("contradicted" if source == "openemr" else "needs_review")
    if source == "openemr":
        wrong = join.model_copy(update={"target_columns": ("id",)})
        wrong_result = reader.capture(
            request.model_copy(update={"profiles": (), "relationships": (wrong,)}), schema
        )
        assert wrong_result.relationships[0].unmatched_source_rows == 5
        names = RelationshipSelection(
            source_table=profile.table,
            source_columns=("fname",),
            target_table=profile.table,
            target_columns=("fname",),
        )
        name_result = reader.capture(
            request.model_copy(update={"profiles": (), "relationships": (names,)}), schema
        )
        assert name_result.relationships[0].target_duplicate_key_groups == 1
        assert name_result.relationships[0].status == "contradicted"
    limited = reader.capture(
        request.model_copy(update={"policy": EvidencePolicy(max_check_rows=2)}), schema
    )
    assert not limited.relationships[0].complete and limited.relationships[0].status == "incomplete"
    path = tmp_path / "registry.sqlite"
    migrate_registry(path)
    registry = HospitalRegistry(path)
    receipt = registry.save_scan(schema)
    access = registry.begin_evidence_access(receipt.scan_id, request, "fixture-reviewer")
    registry.finish_evidence_access(access, observed)
    registry.close()
    registry = HospitalRegistry(path)
    assert registry.load_evidence(observed.observation_id, config.source_system_id) == observed
    registry.close()
