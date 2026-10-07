from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from datapulse.connectors.base import ColumnProfile, ExtractedBatch, ExtractionRequest
from datapulse.contracts.schema import TableRef


@pytest.mark.parametrize("batch_size", [0, 1001])
def test_extraction_limits_and_no_raw_sql(batch_size):
    with pytest.raises(ValidationError):
        ExtractionRequest(
            table=TableRef(namespace="demo", name="patient"),
            columns=("id",),
            key_columns=("id",),
            batch_size=batch_size,
        )
    with pytest.raises(ValidationError):
        ExtractionRequest.model_validate(
            {
                "table": {"namespace": "demo", "name": "patient"},
                "columns": ["id"],
                "key_columns": ["id"],
                "sql": "SELECT *",
            }
        )


def test_extraction_keys_required_in_projection():
    with pytest.raises(ValidationError):
        ExtractionRequest(
            table=TableRef(namespace="demo", name="patient"),
            columns=("name",),
            key_columns=("id",),
        )


def test_profile_counts_and_fingerprint_validated():
    payload = {
        "schema_fingerprint": "a" * 64,
        "table": {"namespace": "demo", "name": "patient"},
        "column": "gender",
        "sampled_at": datetime.now(UTC).isoformat(),
        "sampling_method": "bounded",
        "scope": "first rows",
        "sample_count": 3,
        "null_count": 1,
        "distinct_values": ["M", "F"],
        "truncated": True,
    }
    assert ColumnProfile.model_validate(payload).sample_count == 3
    with pytest.raises(ValidationError):
        ColumnProfile.model_validate({**payload, "null_count": 4})
    with pytest.raises(ValidationError):
        ColumnProfile.model_validate({**payload, "schema_fingerprint": "invalid"})


def test_extracted_rows_are_json_serializable_and_bounded():
    batch = ExtractedBatch(
        rows=({"id": "source-1", "gender": "M"},),
        next_cursor=None,
        schema_fingerprint="a" * 64,
        source_snapshot="snapshot-1",
    )
    assert '"source-1"' in batch.model_dump_json()
    with pytest.raises(ValidationError):
        ExtractedBatch.model_validate({**batch.model_dump(), "rows": [{}] * 1001})
