from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from datapulse.contracts.schema import (
    ColumnSchema,
    DatabaseSchema,
    ForeignKeySchema,
    IndexSchema,
    RelationshipHint,
    TableRef,
    TableSchema,
)


def schema_payload():
    return {
        "source_system_id": str(uuid4()),
        "database_name": "synthetic",
        "vendor": "mysql",
        "scanned_at": datetime.now(UTC).isoformat(),
        "tables": [
            {
                "namespace": "synthetic",
                "name": "patient",
                "columns": [
                    {
                        "name": "id",
                        "ordinal": 0,
                        "native_type": "int",
                        "normalized_type": "integer",
                        "nullable": False,
                    },
                    {
                        "name": "name",
                        "ordinal": 1,
                        "native_type": "varchar(100)",
                        "normalized_type": "string",
                        "nullable": True,
                    },
                ],
                "primary_key": ["id"],
                "indexes": [{"name": "idx_name", "columns": ["name"]}],
            },
            {
                "namespace": "synthetic",
                "name": "visit",
                "columns": [
                    {
                        "name": "patient_id",
                        "ordinal": 0,
                        "native_type": "int",
                        "normalized_type": "integer",
                        "nullable": False,
                    }
                ],
                "foreign_keys": [
                    {
                        "name": "fk_patient",
                        "columns": ["patient_id"],
                        "referenced_table": {"namespace": "synthetic", "name": "patient"},
                        "referenced_columns": ["id"],
                    }
                ],
            },
        ],
    }


def test_schema_roundtrip_and_fingerprint_ignore_order_time_comments_and_hints():
    payload = schema_payload()
    schema = DatabaseSchema.model_validate(payload)
    assert DatabaseSchema.model_validate_json(schema.model_dump_json()) == schema
    payload["scanned_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    payload["tables"][0]["comment"] = "New human documentation"
    payload["tables"][0]["columns"][0]["default"] = "different-default"
    payload["tables"][0]["relationship_hints"] = [
        {
            "columns": ["id"],
            "referenced_table": {"namespace": "synthetic", "name": "visit"},
            "referenced_columns": ["patient_id"],
            "evidence": ["inferred name relationship"],
        }
    ]
    payload["tables"][0]["columns"].reverse()
    payload["tables"].reverse()
    assert DatabaseSchema.model_validate(payload).structural_fingerprint() == (
        schema.structural_fingerprint()
    )


@pytest.mark.parametrize("field,value", [("nullable", True), ("native_type", "bigint")])
def test_structural_changes_invalidate_fingerprint(field, value):
    payload = schema_payload()
    before = DatabaseSchema.model_validate(payload).structural_fingerprint()
    payload["tables"][0]["columns"][0][field] = value
    assert DatabaseSchema.model_validate(payload).structural_fingerprint() != before


@pytest.mark.parametrize("fault", ["duplicate_table", "duplicate_column", "bad_pk", "bad_target"])
def test_invalid_schema_rejected(fault):
    payload = schema_payload()
    if fault == "duplicate_table":
        payload["tables"].append(payload["tables"][0])
    elif fault == "duplicate_column":
        payload["tables"][0]["columns"].append(payload["tables"][0]["columns"][0])
    elif fault == "bad_pk":
        payload["tables"][0]["primary_key"] = ["absent"]
    else:
        payload["tables"][1]["foreign_keys"][0]["referenced_columns"] = ["absent"]
    with pytest.raises(ValidationError):
        DatabaseSchema.model_validate(payload)


def test_foreign_keys_outside_scan_preserved():
    payload = schema_payload()
    payload["tables"] = payload["tables"][1:]
    assert len(DatabaseSchema.model_validate(payload).tables[0].foreign_keys) == 1


def test_unknown_types_and_expression_indexes_preserved():
    column = ColumnSchema(
        name="custom",
        ordinal=0,
        native_type="vendor-specific",
        normalized_type="unknown",
        nullable=True,
    )
    index = IndexSchema(name="expression", expression="lower(custom)")
    table = TableSchema(namespace="demo", name="custom", columns=(column,), indexes=(index,))
    assert table.columns[0].native_type == "vendor-specific"
    assert table.indexes[0].expression == "lower(custom)"


def test_fk_arity_and_timezone_and_extra_fields_rejected():
    with pytest.raises(ValidationError):
        ForeignKeySchema(
            name="bad",
            columns=("one", "two"),
            referenced_table=TableRef(namespace="demo", name="target"),
            referenced_columns=("one",),
        )
    payload = schema_payload()
    payload["scanned_at"] = "2026-10-07T12:00:00"
    with pytest.raises(ValidationError):
        DatabaseSchema.model_validate(payload)
    payload = schema_payload()
    payload["password"] = "must-not-be-part-of-schema"
    with pytest.raises(ValidationError):
        DatabaseSchema.model_validate(payload)


def test_hints_are_evidence_labelled_not_declared_foreign_keys():
    hint = RelationshipHint(
        columns=("id",),
        referenced_table=TableRef(namespace="demo", name="other"),
        referenced_columns=("id",),
        evidence=("lexical similarity",),
        confidence=0.4,
    )
    assert hint.confidence == 0.4
    with pytest.raises(ValidationError):
        RelationshipHint.model_validate({**hint.model_dump(), "evidence": []})
