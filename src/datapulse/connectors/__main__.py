"""Source-local JSON health command; credentials are file references, never CLI secrets."""

import argparse
import json
from pathlib import Path

from datapulse.connectors.connection import ConnectionConfig, FileCredentialResolver
from datapulse.connectors.mysql import MySQLConnectionProbe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check authenticated read-only source DB access")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--credentials", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        with args.config.open("rb") as file:
            payload = file.read(65537)
        if len(payload) > 65536:
            raise ValueError("Configuration exceeds bound")
        config = ConnectionConfig.model_validate_json(payload)
    except (OSError, ValueError):
        print(json.dumps({"error": "invalid_configuration"}))
        return 1
    result = MySQLConnectionProbe(config, FileCredentialResolver(args.credentials)).check()
    print(result.model_dump_json())
    return 0 if result.status == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
