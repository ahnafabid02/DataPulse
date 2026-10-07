"""Reproducible, explicitly synthetic metadata benchmark. No hospital records read."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid5

from datapulse.contracts.schema import ColumnSchema, DatabaseSchema, TableRef, TableSchema
from datapulse.mapping.catalog import FHIRCatalog
from datapulse.mapping.contracts import MappingRunInput, MappingScope
from datapulse.mapping.pipeline import MappingPipeline
from datapulse.mapping.provider import LocalModelConfig, OllamaProvider

NAMESPACE = UUID("960f0f81-74f6-41c9-bf6e-c4ddbd0a5d78")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=Path("tests/fixtures/m4_mapping_cases.json"))
    args = parser.parse_args()
    catalog = FHIRCatalog.load(args.package)
    provider = OllamaProvider(LocalModelConfig.model_validate_json(args.model_config.read_bytes()))
    results = []
    for case in json.loads(args.cases.read_text()):
        scan = DatabaseSchema(
            source_system_id=uuid5(NAMESPACE, "synthetic-source"),
            database_name="synthetic",
            vendor="mariadb",
            scanned_at=datetime.now(UTC),
            tables=(
                TableSchema(
                    namespace="synthetic",
                    name="patient",
                    columns=(
                        ColumnSchema(
                            name=case["column"],
                            ordinal=0,
                            native_type=case["native_type"],
                            normalized_type=case["normalized_type"],
                            nullable=True,
                        ),
                    ),
                ),
            ),
        )
        request = MappingRunInput(
            run_id=uuid5(NAMESPACE, case["id"] + datetime.now(UTC).isoformat()),
            source_system_id=scan.source_system_id,
            database_name=scan.database_name,
            schema_fingerprint=scan.structural_fingerprint(),
            schema_scan_id=uuid5(NAMESPACE, case["id"]),
            scope=MappingScope(tables=(TableRef(namespace="synthetic", name="patient"),)),
        )
        started = time.monotonic()
        run = MappingPipeline(catalog, provider).run(request, scan)
        actual = [p.field.target_path for p in run.proposals]
        correct = (
            actual == [case["expected"]]
            if case["expected"]
            else not actual and bool(run.unresolved_fields)
        )
        entry = {
            "case": case["id"],
            "expected": case["expected"],
            "actual": actual,
            "correct": correct,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "status": run.status,
            "unresolved_reasons": [u.reason for u in run.unresolved_fields],
            "attempts": run.provider_run_metadata["attempts"],
            "model_metrics": provider.metadata(),
        }
        results.append(entry)
        print(
            json.dumps({k: entry[k] for k in ("case", "actual", "correct", "elapsed_seconds")}),
            flush=True,
        )
    report = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "synthetic_only": True,
        "catalog_sha256": catalog.digest,
        "logical_cpu_count": os.cpu_count(),
        "model": provider.metadata(),
        "correct": sum(r["correct"] for r in results),
        "total": len(results),
        "cases": results,
        "limitations": "Small synthetic metadata benchmark; no clinical acceptance",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
