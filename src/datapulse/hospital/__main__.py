"""Hospital-local bounded evidence capture; stdout contains identifiers and counts."""

import argparse
import json
from pathlib import Path
from typing import Never
from uuid import UUID

from datapulse.connectors.connection import ConnectionConfig, FileCredentialResolver
from datapulse.connectors.evidence import EvidenceRequest, MySQLEvidenceReader
from datapulse.hospital.coverage import inventory
from datapulse.hospital.registry import HospitalRegistry


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ValueError("invalid_arguments")


def _read(path: Path) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError("input_limit")
    return data


def main(argv: list[str] | None = None) -> int:
    registry = None
    access_id = None
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("command", choices=("capture", "inventory"))
        parser.add_argument("--registry", type=Path, required=True)
        parser.add_argument("--scan-id", type=UUID, required=True)
        parser.add_argument("--source-id", type=UUID)
        parser.add_argument("--config", type=Path)
        parser.add_argument("--credentials", type=Path)
        parser.add_argument("--request", type=Path)
        parser.add_argument("--actor")
        parser.add_argument("--output", type=Path)
        args = parser.parse_args(argv)
        registry = HospitalRegistry(args.registry)
        if args.command == "inventory":
            if args.source_id is None or args.output is None:
                raise ValueError("invalid_inventory_arguments")
            result = inventory(registry.load_scan(args.scan_id, args.source_id))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "source_system_id": str(result.source_system_id),
                        "fields": len(result.fields),
                        "complete_clinical_mapping": False,
                    }
                )
            )
            return 0
        if any(
            value is None for value in (args.request, args.config, args.credentials, args.actor)
        ):
            raise ValueError("invalid_capture_arguments")
        request = EvidenceRequest.model_validate_json(_read(args.request))
        config = ConnectionConfig.model_validate_json(_read(args.config))
        schema = registry.load_scan(args.scan_id, request.source_system_id)
        access_id = registry.begin_evidence_access(args.scan_id, request, args.actor)
        observation = MySQLEvidenceReader(config, FileCredentialResolver(args.credentials)).capture(
            request, schema
        )
        registry.finish_evidence_access(access_id, observation)
        access_id = None
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(observation.model_dump_json(indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "observation_id": str(observation.observation_id),
                    "source_system_id": str(observation.source_system_id),
                    "profiles": len(observation.profiles),
                    "relationships": len(observation.relationships),
                    "approved": False,
                }
            )
        )
        return 0
    except Exception as error:
        category = getattr(error, "category", "evidence_unavailable")
        if registry is not None and access_id is not None:
            try:
                registry.finish_evidence_access(access_id, None, category)
            except Exception:
                category = "evidence_unavailable"
        # Unknown categories never reflect submitted arguments, bodies or driver text.
        safe = {
            "source_mismatch",
            "schema_changed",
            "scope_unavailable",
            "timeout",
            "limit_exceeded",
            "value_limit_exceeded",
            "unsupported_snapshot_engine",
            "unsupported_relationship_type",
            "registry_revision_mismatch",
            "registry_not_provisioned",
            "invalid_actor",
            "scan_unavailable",
        }
        print(json.dumps({"error": category if category in safe else "evidence_unavailable"}))
        return 1
    finally:
        if registry is not None:
            registry.close()


if __name__ == "__main__":
    raise SystemExit(main())
