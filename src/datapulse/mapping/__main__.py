"""Explicit hospital-local catalog/registry/scan/proposal commands with safe summaries."""

import argparse
import json
from pathlib import Path
from typing import Never
from uuid import UUID, uuid4

from datapulse.connectors.connection import ConnectionConfig, FileCredentialResolver
from datapulse.connectors.introspection import MySQLSchemaScanner, ScanPolicy
from datapulse.contracts.schema import TableRef
from datapulse.hospital.registry import HospitalRegistry, migrate_registry
from datapulse.mapping.catalog import FHIRCatalog, cache_package
from datapulse.mapping.contracts import FieldRef, MappingRunInput, MappingRunResult, MappingScope
from datapulse.mapping.pipeline import MappingPipeline, proposal_reuse_key
from datapulse.mapping.provider import LocalModelConfig, OllamaProvider


def _read(path: Path, maximum: int = 65536) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("input_limit")
    return data


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        # argparse's default error echoes unknown submitted arguments/UUID values.
        raise ValueError("Invalid arguments")


def main(argv: list[str] | None = None) -> int:
    parser = _SafeParser(description="Hospital-local M4 preparation and proposals")
    commands = parser.add_subparsers(dest="command", required=True)
    cache = commands.add_parser("catalog")
    cache.add_argument("--cache", type=Path, default=Path("data/fhir"))
    init = commands.add_parser("registry-init")
    init.add_argument("--registry", type=Path, required=True)
    scan = commands.add_parser("scan")
    scan.add_argument("--config", type=Path, required=True)
    scan.add_argument("--credentials", type=Path, required=True)
    scan.add_argument("--policy", type=Path)
    scan.add_argument("--registry", type=Path, required=True)
    scan.add_argument("--output", type=Path)
    propose = commands.add_parser("propose")
    propose.add_argument("--registry", type=Path, required=True)
    propose.add_argument("--source-id", type=UUID, required=True)
    propose.add_argument("--scan-id", type=UUID, required=True)
    propose.add_argument("--package", type=Path, required=True)
    propose.add_argument("--model-config", type=Path, required=True)
    propose.add_argument(
        "--output", type=Path, help="Save proposed results to a protected local JSON file"
    )
    propose.add_argument(
        "--force", action="store_true", help="Create new proposals even if inputs match"
    )
    propose.add_argument(
        "--fields",
        type=Path,
        required=True,
        help="JSON array of explicit qualified FieldRef objects; maximum 40",
    )
    registry = None
    try:
        if args := parser.parse_args(argv):
            if args.command == "catalog":
                path = cache_package(args.cache)
                catalog = FHIRCatalog.load(path)
                print(
                    json.dumps(
                        {
                            "status": "verified",
                            "package": "hl7.fhir.r4.core#4.0.1",
                            "sha256": catalog.digest,
                        }
                    )
                )
                return 0
            if args.command == "registry-init":
                migrate_registry(args.registry)
                print(json.dumps({"status": "provisioned", "revision": "hospital_0003"}))
                return 0
            registry = HospitalRegistry(args.registry)
            if args.command == "scan":
                config = ConnectionConfig.model_validate_json(_read(args.config))
                policy = (
                    ScanPolicy.model_validate_json(_read(args.policy))
                    if args.policy
                    else ScanPolicy()
                )
                schema = MySQLSchemaScanner(
                    config, FileCredentialResolver(args.credentials), policy
                ).introspect(config.source_system_id)
                receipt = registry.save_scan(schema)
                if args.output:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(schema.model_dump_json(indent=2), encoding="utf-8")
                print(receipt.model_dump_json())
                return 0
            schema = registry.load_scan(args.scan_id, args.source_id)
            fields = tuple(FieldRef.model_validate(f) for f in json.loads(_read(args.fields)))
            scope = tuple(sorted({(f.table.namespace, f.table.name) for f in fields}))
            request = MappingRunInput(
                run_id=uuid4(),
                source_system_id=args.source_id,
                database_name=schema.database_name,
                schema_fingerprint=schema.structural_fingerprint(),
                schema_scan_id=args.scan_id,
                scope=MappingScope(tables=tuple(TableRef(namespace=n, name=t) for n, t in scope)),
            )
            provider = OllamaProvider(
                LocalModelConfig.model_validate_json(_read(args.model_config))
            )
            catalog = FHIRCatalog.load(args.package)
            reuse_key = proposal_reuse_key(request, schema, fields, catalog, provider)
            cached = None if args.force else registry.find_run(args.source_id, reuse_key)
            if cached:
                result = MappingRunResult.model_validate(cached)
                if result.source_system_id != args.source_id or (
                    result.schema_fingerprint != request.schema_fingerprint
                ):
                    raise ValueError("cached_run_identity_mismatch")
            else:
                result = MappingPipeline(catalog, provider).run(request, schema, fields)
                registry.save_run(args.scan_id, args.source_id, result)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "run_id": str(result.run_id),
                        "status": result.status,
                        "proposals": len(result.proposals),
                        "unresolved": len(result.unresolved_fields),
                        "approved": False,
                        "reused": cached is not None,
                    }
                )
            )
            return 0 if result.status != "failed" else 1
    except Exception as error:
        # Only known categories are printed; never arbitrary provider/DB/file errors.
        code = getattr(error, "category", None)
        safe = {
            "limit_exceeded",
            "scope_unavailable",
            "schema_changed",
            "source_mismatch",
            "timeout",
            "credential_unavailable",
            "authentication_failed",
            "database_denied",
            "connection_unavailable",
            "unsafe_privileges",
            "invalid_metadata",
            "database_unavailable",
            "vendor_mismatch",
            "tls_failed",
            "package_checksum_mismatch",
            "package_manifest_mismatch",
            "package_unavailable",
            "missing_core_definitions",
            "resource_unavailable",
            "invalid_package",
            "registry_not_provisioned",
            "registry_revision_mismatch",
            "registry_write_failed",
            "scan_unavailable",
            "scan_integrity_failed",
            "run_source_mismatch",
            "run_fingerprint_mismatch",
            "invalid_field_scope_or_limit",
            "invalid_scope",
            "scan_identity_mismatch",
        }
        print(json.dumps({"error": code if code in safe else "operation_failed"}))
        return 1
    finally:
        if registry is not None:
            registry.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
