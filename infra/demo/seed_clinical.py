"""Seed only the fixed disposable EHRs with generated fictional records, never exports."""

import hashlib
import json
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from demo import LOCAL, SOURCES, compose

VERSION = "fictional-clinical-v1"
DATE = "2020-01-01 12:00:00"


def _uuid(source: str, table: str, key: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"datapulse/{VERSION}/{source}/{table}/{key}"))


def fixtures(source: str) -> list[tuple[str, str, list[dict[str, object]]]]:
    if source == "openmrs":

        def record(table: str, key: str, identity: int, **values: object) -> dict[str, object]:
            return {
                key: identity,
                "creator": 1,
                "date_created": DATE,
                "uuid": _uuid(source, table, identity),
                **values,
            }

        result = [
            (
                "patient_identifier_type",
                "patient_identifier_type_id",
                [
                    record(
                        "patient_identifier_type",
                        "patient_identifier_type_id",
                        900001,
                        name="DataPulse fictional identifier",
                        required=0,
                        check_digit=0,
                        uniqueness_behavior="NON_UNIQUE",
                    )
                ],
            ),
            (
                "location",
                "location_id",
                [record("location", "location_id", 900001, name="DataPulse fictional ward")],
            ),
            (
                "encounter_type",
                "encounter_type_id",
                [
                    record(
                        "encounter_type",
                        "encounter_type_id",
                        900001,
                        name="DataPulse fictional visit",
                    )
                ],
            ),
            (
                "concept",
                "concept_id",
                [
                    record(
                        "concept",
                        "concept_id",
                        900001,
                        datatype_id=1,
                        class_id=1,
                        is_set=0,
                        retired=0,
                    )
                ],
            ),
            (
                "concept_name",
                "concept_name_id",
                [
                    record(
                        "concept_name",
                        "concept_name_id",
                        900001,
                        concept_id=900001,
                        name="DataPulse fictional measurement",
                        locale="en",
                        locale_preferred=1,
                        concept_name_type="FULLY_SPECIFIED",
                    )
                ],
            ),
            (
                "concept_numeric",
                "concept_id",
                [{"concept_id": 900001, "units": "demo-unit", "allow_decimal": 1}],
            ),
        ]
        persons, patients, names, identifiers = [], [], [], []
        for index, (given, family, gender, birthdate) in enumerate(
            (
                ("Fictional Avery", "Demo", "M", "1980-02-03"),
                ("Fictional Avery", "Demo", "F", "1980-02-03"),
                ("Fictional Casey", None, "U", None),
            ),
            start=1,
        ):
            key = 900000 + index
            persons.append(
                record(
                    "person",
                    "person_id",
                    key,
                    gender=gender,
                    birthdate=birthdate,
                    dead=0,
                    voided=0,
                    birthdate_estimated=0,
                )
            )
            patients.append(
                {
                    "patient_id": key,
                    "creator": 1,
                    "date_created": DATE,
                    "voided": 0,
                    "allergy_status": "Unknown",
                }
            )
            names.append(
                record(
                    "person_name",
                    "person_name_id",
                    key,
                    person_id=key,
                    given_name=given,
                    family_name=family,
                    preferred=1,
                    voided=0,
                )
            )
            identifiers.append(
                record(
                    "patient_identifier",
                    "patient_identifier_id",
                    key,
                    patient_id=key,
                    identifier=("DEMO-01", "DEMO-001", "DEMO-03")[index - 1],
                    identifier_type=900001,
                    location_id=900001,
                    preferred=1,
                    voided=0,
                )
            )
        result.extend(
            [
                ("person", "person_id", persons),
                ("patient", "patient_id", patients),
                ("person_name", "person_name_id", names),
                ("patient_identifier", "patient_identifier_id", identifiers),
            ]
        )
        encounters, observations = [], []
        for index, patient in enumerate((900001, 900001, 900002, 900003), start=1):
            key = 900000 + index
            when = f"2020-01-0{index} 12:00:00"
            encounters.append(
                record(
                    "encounter",
                    "encounter_id",
                    key,
                    patient_id=patient,
                    encounter_type=900001,
                    encounter_datetime=when,
                    location_id=900001,
                    voided=0,
                )
            )
            observations.append(
                record(
                    "obs",
                    "obs_id",
                    key,
                    person_id=patient,
                    concept_id=900001,
                    encounter_id=key,
                    obs_datetime=when,
                    location_id=900001,
                    value_numeric=100 + index,
                    status="FINAL",
                    voided=0,
                )
            )
        result.extend([("encounter", "encounter_id", encounters), ("obs", "obs_id", observations)])
        return result
    if source != "openemr":
        raise ValueError("unknown_fixture")
    patients = []
    for index, (given, family, sex, birthdate) in enumerate(
        (
            ("Fictional Avery", "Demo", "Male", "1980-02-03"),
            ("Fictional Avery", "Demo", "Female", "1980-02-03"),
            ("Fictional Casey", "", "Unknown", None),
        ),
        start=1,
    ):
        patients.append(
            {
                "id": 900000 + index,
                "pid": 910000 + index,
                "pubpid": ("DEMO-01", "DEMO-001", "DEMO-03")[index - 1],
                "uuid": uuid5(NAMESPACE_URL, f"datapulse/{VERSION}/{source}/patient/{index}").bytes,
                "fname": given,
                "lname": family,
                "sex": sex,
                "DOB": birthdate,
                "date": DATE,
                "last_updated": DATE,
            }
        )
    encounters, forms, vitals = [], [], []
    for index, patient in enumerate((910001, 910001, 910002, 910003, 919999), start=1):
        key = 900000 + index
        encounter = 920000 + index
        when = f"2020-01-0{index} 12:00:00"
        encounters.append(
            {
                "id": key,
                "pid": patient,
                "encounter": encounter,
                "date": when,
                "uuid": uuid5(
                    NAMESPACE_URL, f"datapulse/{VERSION}/{source}/encounter/{index}"
                ).bytes,
                "reason": "Fictional relationship test" if index == 5 else "Fictional visit",
                "facility_id": 3,
                "last_update": DATE,
            }
        )
        forms.append(
            {
                "id": 900000 + index,
                "pid": patient,
                "encounter": encounter,
                "form_id": key,
                "form_name": "New Patient Encounter",
                "formdir": "newpatient",
                "user": "demo_admin",
                "date": when,
                "deleted": 0,
            }
        )
        if index < 5:
            vitals.append(
                {
                    "id": key,
                    "pid": patient,
                    "date": when,
                    "user": "demo_admin",
                    "bps": 100 + index,
                    "bpd": 60 + index,
                    "activity": 1,
                    "last_updated": DATE,
                }
            )
            forms.append(
                {
                    "id": 901000 + index,
                    "pid": patient,
                    "encounter": encounter,
                    "form_id": key,
                    "form_name": "Vitals",
                    "formdir": "vitals",
                    "user": "demo_admin",
                    "date": when,
                    "deleted": 0,
                }
            )
    return [
        ("patient_data", "id", patients),
        ("form_encounter", "id", encounters),
        ("form_vitals", "id", vitals),
        ("forms", "id", forms),
    ]


def _literal(value: object) -> str:
    from pymysql.converters import escape_string

    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    if isinstance(value, int):
        return str(value)
    return "'" + escape_string(str(value)) + "'"


def _run(source: str, sql: str) -> str:
    result = compose(
        "exec",
        "-T",
        f"{source}-db",
        "mariadb",
        "--defaults-extra-file=/run/datapulse/root.cnf",
        "--batch",
        "--skip-column-names",
        input_text=sql,
    )
    if result.returncode:
        raise ValueError("fictional_seed_failed")
    return result.stdout.strip()


def _checks(source: str, plan: list[tuple[str, str, list[dict[str, object]]]]) -> tuple[int, str]:
    count = 0
    checks = []
    for table, _key, rows in plan:
        for row in rows:
            predicates = " AND ".join(
                f"BINARY `{c}` <=> BINARY {_literal(v)}" for c, v in row.items()
            )
            checks.append(f"SELECT COUNT(*) FROM `{source}`.`{table}` WHERE {predicates};")
            count += 1
    return count, "\n".join(checks)


def verify_seed(source: str) -> bool:
    plan = fixtures(source)
    expected, checks = _checks(source, plan)
    matches = _run(source, checks).splitlines()
    if len(matches) != expected or any(value != "1" for value in matches):
        return False
    clinical = {"patient", "encounter", "obs"} if source == "openmrs" else {t for t, _, _ in plan}
    selected = [(table, rows) for table, _, rows in plan if table in clinical]
    totals = _run(
        source, "\n".join(f"SELECT COUNT(*) FROM `{source}`.`{table}`;" for table, _ in selected)
    ).splitlines()
    if totals != [str(len(rows)) for _, rows in selected]:
        return False
    receipt = LOCAL / f"{source}-seed-rows.json"
    if not receipt.exists() or json.loads(receipt.read_text()) != _row_digests(source):
        return False
    return True


def _row_digests(source: str) -> list[str]:
    statements = []
    for table, key, rows in fixtures(source):
        columns = _run(
            source,
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            f"WHERE TABLE_SCHEMA='{source}' AND TABLE_NAME='{table}' "
            "ORDER BY ORDINAL_POSITION;",
        ).splitlines()
        if not columns:
            raise ValueError("fixture_schema_unavailable")
        expressions = ",".join(
            "COALESCE(HEX(CAST(`" + c.replace("`", "``") + "` AS BINARY)),'NULL')" for c in columns
        )
        keys = ",".join(str(row[key]) for row in rows)
        statements.append(
            f"SELECT SHA2(CONCAT_WS('|',{expressions}),256) FROM "
            f"`{source}`.`{table}` WHERE `{key}` IN ({keys}) ORDER BY `{key}`;"
        )
    return _run(source, "\n".join(statements)).splitlines()


def seed() -> None:
    from verify_environment import verify

    state = verify()
    if not all(
        s["pinned_metadata_matches"]
        and s["application_ready"]
        and str(s["database_version"]).startswith("10.11.7" if name == "openmrs" else "12.3.3")
        for name, s in state.items()
    ):
        raise ValueError("pinned_environment_unavailable")
    # Guard both sources before any write. Repeat is accepted only for exact fixtures.
    completed = {source: verify_seed(source) for source in SOURCES}
    for source in SOURCES:
        if completed[source]:
            continue
        plan = fixtures(source)
        clinical = (
            {"patient", "encounter", "obs"} if source == "openmrs" else {t for t, _, _ in plan}
        )
        checks = []
        expected = []
        for table, key, rows in plan:
            keys = ",".join(str(row[key]) for row in rows)
            checks.append(f"SELECT COUNT(*) FROM `{source}`.`{table}` WHERE `{key}` IN ({keys});")
            expected.append("0")
            if table in clinical:
                checks.append(f"SELECT COUNT(*) FROM `{source}`.`{table}`;")
                expected.append("0")
            checks.append(
                "SELECT ENGINE FROM information_schema.TABLES "
                f"WHERE TABLE_SCHEMA='{source}' AND TABLE_NAME='{table}';"
            )
            expected.append("InnoDB")
        if _run(source, "\n".join(checks)).splitlines() != expected:
            raise ValueError("unrecognized_or_nontransactional_fixture")
    # Validate pinned installer support identities, rather than assuming defaults.
    if (
        _run("openmrs", "SELECT COUNT(*) FROM openmrs.users WHERE user_id=1;") != "1"
        or (
            _run(
                "openmrs",
                "SELECT COUNT(*) FROM openmrs.concept_datatype WHERE concept_datatype_id=1 "
                "AND hl7_abbreviation='NM';",
            )
            != "1"
        )
        or (
            _run(
                "openmrs",
                "SELECT COUNT(*) FROM openmrs.concept_class "
                "WHERE concept_class_id=1 AND name='Test';",
            )
            != "1"
        )
    ):
        raise ValueError("support_identity_unavailable")
    if _run("openemr", "SELECT COUNT(*) FROM openemr.facility WHERE id=3;") != "1" or (
        _run("openemr", "SELECT COUNT(*) FROM openemr.users WHERE username='demo_admin';") != "1"
    ):
        raise ValueError("support_identity_unavailable")
    for source in SOURCES:
        if not completed[source]:
            statements = ["START TRANSACTION;"]
            for table, _, rows in fixtures(source):
                for row in rows:
                    columns = ",".join(f"`{c}`" for c in row)
                    values = ",".join(_literal(v) for v in row.values())
                    statements.append(
                        f"INSERT INTO `{source}`.`{table}` ({columns}) VALUES ({values});"
                    )
            statements.append("COMMIT;")
            _run(source, "\n".join(statements))
            LOCAL.mkdir(parents=True, exist_ok=True)
            (LOCAL / f"{source}-seed-rows.json").write_text(
                json.dumps(_row_digests(source)), encoding="utf-8"
            )
        if not verify_seed(source):
            raise ValueError("fictional_seed_verification_failed")
    digest = hashlib.sha256(
        json.dumps(
            {s: fixtures(s) for s in SOURCES},
            sort_keys=True,
            default=lambda v: v.hex() if isinstance(v, bytes) else str(v),
        ).encode()
    ).hexdigest()
    LOCAL.mkdir(parents=True, exist_ok=True)
    (LOCAL / "clinical-seed.json").write_text(
        json.dumps({"version": VERSION, "digest": digest, "verified_sources": list(SOURCES)}),
        encoding="utf-8",
    )
    print(
        json.dumps({"seed": VERSION, "sources": 2, "verified": True, "patient_rows_per_source": 3})
    )


def main() -> int:
    try:
        if len(sys.argv) > 1 and sys.argv[1:] != ["verify"]:
            raise ValueError("invalid_arguments")
        if sys.argv[1:] == ["verify"]:
            accepted = all(verify_seed(source) for source in SOURCES)
            print(json.dumps({"seed": VERSION, "verified": accepted}))
            return 0 if accepted else 1
        seed()
        return 0
    except Exception:
        print(json.dumps({"error": "fictional_seed_unavailable"}))
        return 1


if __name__ == "__main__":
    # Use the same installed Docker Desktop helper discovery as the demo launcher.
    import os

    helper = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/DockerDesktop/resources/bin"
    if helper.exists():
        os.environ["PATH"] = str(helper) + os.pathsep + os.environ["PATH"]
    raise SystemExit(main())
