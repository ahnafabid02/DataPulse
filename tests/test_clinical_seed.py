"""Fictional seed reproducibility and refusal boundaries without source writes."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "infra/demo"))
SPEC = importlib.util.spec_from_file_location("clinical_seed", ROOT / "infra/demo/seed_clinical.py")
assert SPEC and SPEC.loader
seed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seed)


def test_fictional_plan_is_deterministic_and_preserves_source_key_meaning():
    assert seed.fixtures("openmrs") == seed.fixtures("openmrs")
    assert seed.fixtures("openemr") == seed.fixtures("openemr")
    emr = {t: rows for t, _, rows in seed.fixtures("openemr")}
    assert len(emr["patient_data"]) == 3 and len(emr["form_encounter"]) == 5
    assert all(r["id"] != r["pid"] for r in emr["patient_data"])
    assert all(r["id"] != r["encounter"] for r in emr["form_encounter"])
    assert all(isinstance(r["uuid"], bytes) and len(r["uuid"]) == 16 for r in emr["patient_data"])
    assert (
        len({r["pid"] for r in emr["form_encounter"]} - {r["pid"] for r in emr["patient_data"]})
        == 1
    )
    assert len(emr["forms"]) == len(emr["form_encounter"]) + len(emr["form_vitals"])
    for table, column in (
        ("patient_data", "last_updated"),
        ("form_encounter", "last_update"),
        ("form_vitals", "last_updated"),
    ):
        assert all(row[column] == seed.DATE for row in emr[table])
    mrs = {t: rows for t, _, rows in seed.fixtures("openmrs")}
    assert {r["person_id"] for r in mrs["person"]} == {r["patient_id"] for r in mrs["patient"]}
    assert all(
        r["patient_id"] in {p["patient_id"] for p in mrs["patient"]} for r in mrs["encounter"]
    )
    assert any(p["birthdate"] is None for p in mrs["person"])
    assert len({r["given_name"] for r in mrs["person_name"]}) < 3
    with pytest.raises(ValueError):
        seed.fixtures("arbitrary-hospital")


def _accepted(monkeypatch):
    state = {
        name: {
            "pinned_metadata_matches": True,
            "application_ready": True,
            "database_version": version,
        }
        for name, version in (("openmrs", "10.11.7"), ("openemr", "12.3.3"))
    }
    monkeypatch.setitem(sys.modules, "verify_environment", SimpleNamespace(verify=lambda: state))
    return state


def test_seed_refuses_changed_pins_before_writes(monkeypatch):
    state = _accepted(monkeypatch)
    state["openemr"]["database_version"] = "12.4.0"
    called = []
    monkeypatch.setattr(seed, "_run", lambda *args: called.append(args))
    with pytest.raises(ValueError, match="pinned_environment"):
        seed.seed()
    assert called == []


@pytest.mark.parametrize("bad_source", ["openmrs", "openemr"])
def test_seed_checks_both_sources_before_first_insert(monkeypatch, bad_source):
    _accepted(monkeypatch)
    monkeypatch.setattr(seed, "verify_seed", lambda _: False)
    queries = []

    def run(source, sql):
        queries.append(sql)
        return (
            "unexpected"
            if source == bad_source
            else "\n".join(
                "InnoDB" if "SELECT ENGINE" in line else "0" for line in sql.splitlines()
            )
        )

    monkeypatch.setattr(seed, "_run", run)
    with pytest.raises(ValueError, match="unrecognized"):
        seed.seed()
    assert not any("INSERT" in sql for sql in queries)


def test_seed_repeat_only_verifies_and_preserves_owned_rows(monkeypatch, tmp_path):
    _accepted(monkeypatch)
    monkeypatch.setattr(seed, "LOCAL", tmp_path)
    monkeypatch.setattr(seed, "verify_seed", lambda _: True)
    queries = []

    def run(source, sql):
        queries.append(sql)
        return "1"

    monkeypatch.setattr(seed, "_run", run)
    seed.seed()
    assert not any("INSERT" in sql or "DELETE" in sql or "UPDATE" in sql for sql in queries)
    assert (tmp_path / "clinical-seed.json").is_file()


def test_seed_validation_checks_exact_values_counts_and_integrity_receipt(monkeypatch, tmp_path):
    monkeypatch.setattr(seed, "LOCAL", tmp_path)
    plan = seed.fixtures("openemr")
    expected, _ = seed._checks("openemr", plan)
    results = iter(("\n".join(["1"] * expected), "\n".join(str(len(rows)) for _, _, rows in plan)))
    monkeypatch.setattr(seed, "_run", lambda *_: next(results))
    assert not seed.verify_seed("openemr"), "No receipt must not recognize existing rows"
    (tmp_path / "openemr-seed-rows.json").write_text('["original"]')
    results = iter(("\n".join(["1"] * expected), "\n".join(str(len(rows)) for _, _, rows in plan)))
    monkeypatch.setattr(seed, "_row_digests", lambda _: ["modified"])
    assert not seed.verify_seed("openemr"), "Changes in unprojected columns must be rejected"


def _reproduction_module():
    spec = importlib.util.spec_from_file_location(
        "clinical_reproduction", ROOT / "infra/demo/reproduce_clinical.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reproduction_refuses_reset_when_fixture_is_not_owned(monkeypatch):
    module = _reproduction_module()
    monkeypatch.setattr(module, "verify", lambda: {"openmrs": {"accepted": True}})
    monkeypatch.setattr(module, "verify_seed", lambda _: False)
    reset_calls = []
    monkeypatch.setattr(module, "reset", lambda: reset_calls.append(True))
    with pytest.raises(ValueError, match="unrecognized"):
        module.reproduce()
    assert reset_calls == []


def test_reproduction_records_full_row_digest_mismatch(monkeypatch, tmp_path):
    module = _reproduction_module()
    monkeypatch.setattr(module, "LOCAL", tmp_path)
    monkeypatch.setattr(module, "verify", lambda: {"openmrs": {"accepted": True}})
    monkeypatch.setattr(module, "verify_seed", lambda _: True)
    monkeypatch.setattr(module, "_fingerprints", lambda: {"openmrs": "same"})
    rows = iter(({"openmrs": ["before"]}, {"openmrs": ["after"]}))
    monkeypatch.setattr(module, "_rows", lambda: next(rows))
    monkeypatch.setattr(module, "compose", lambda *a: SimpleNamespace(returncode=0))
    for name in ("reset", "wait_for_installers", "provision", "seed"):
        monkeypatch.setattr(module, name, lambda: None)
    result = module.reproduce()
    assert result["structural_fingerprints_equal"] and not result["full_seed_row_digests_equal"]
    assert (tmp_path / "clinical-reproduction.json").is_file()
