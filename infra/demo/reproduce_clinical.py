"""Reset only recognized fictional sources, then verify complete seed reproducibility."""

import argparse
import json
import os
from pathlib import Path

from demo import LOCAL, SOURCES, compose, provision, reset, wait_for_installers
from seed_clinical import VERSION, seed, verify_seed
from verify_environment import verify

from datapulse.connectors.connection import ConnectionConfig, FileCredentialResolver
from datapulse.connectors.introspection import MySQLSchemaScanner, ScanPolicy


def _fingerprints() -> dict[str, str]:
    result = {}
    for source in SOURCES:
        config = ConnectionConfig.model_validate_json((LOCAL / f"{source}.json").read_bytes())
        schema = MySQLSchemaScanner(
            config, FileCredentialResolver(LOCAL / "credentials.json"), ScanPolicy()
        ).introspect(config.source_system_id)
        result[source] = schema.structural_fingerprint()
    return result


def _rows() -> dict[str, list[str]]:
    return {
        source: json.loads((LOCAL / f"{source}-seed-rows.json").read_text()) for source in SOURCES
    }


def reproduce() -> dict[str, object]:
    if not all(item["accepted"] for item in verify().values()) or not all(
        verify_seed(source) for source in SOURCES
    ):
        raise ValueError("Refusing a reset of unrecognized source data")
    before, rows_before = _fingerprints(), _rows()
    reset()
    if compose("up", "-d").returncode:
        raise ValueError("Startup failed")
    wait_for_installers()
    provision()
    seed()
    result = {
        "seed": VERSION,
        "structural_fingerprints_equal": before == _fingerprints(),
        "full_seed_row_digests_equal": rows_before == _rows(),
        "both_seeds_verified": all(verify_seed(source) for source in SOURCES),
    }
    (LOCAL / "clinical-reproduction.json").write_text(json.dumps(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset-fictional-sources",
        action="store_true",
        required=True,
        help="Remove only the recognized dedicated EHR volumes; preserve central/evidence data",
    )
    parser.parse_args()
    try:
        result = reproduce()
        print(json.dumps(result))
        return (
            0
            if all(
                result[key]
                for key in (
                    "structural_fingerprints_equal",
                    "full_seed_row_digests_equal",
                    "both_seeds_verified",
                )
            )
            else 1
        )
    except (Exception, SystemExit):
        print(json.dumps({"error": "fictional_reproduction_unavailable"}))
        return 1


if __name__ == "__main__":
    helper = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/DockerDesktop/resources/bin"
    if helper.exists():
        os.environ["PATH"] = str(helper) + os.pathsep + os.environ["PATH"]
    raise SystemExit(main())
