"""Operate only the dedicated fictional M3 EHR environment; never print secrets."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "infra/demo"
LOCAL = ROOT / ".tmp/m3-demo"
PROJECT = "datapulse-m3-demo"
SOURCES = {
    "openmrs": ("openmrs", 13306, "0385fb0c-b004-4a57-9523-9e53fb9af033"),
    "openemr": ("openemr", 13307, "aa5874e0-0482-4621-805d-afb2ad244cd4"),
}


def compose(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            PROJECT,
            "--env-file",
            str(DEMO / ".env"),
            "-f",
            str(DEMO / "compose.yaml"),
            *args,
        ],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def initialize() -> None:
    LOCAL.mkdir(parents=True, exist_ok=True)
    env_file = DEMO / ".env"
    if env_file.exists():
        print("Existing local demo credentials retained.")
    else:
        values = {
            f"{source.upper()}_{kind}_PASSWORD": (
                "Aa9" + secrets.token_hex(24) if kind == "ADMIN" else secrets.token_hex(24)
            )
            for source in SOURCES
            for kind in ("ROOT", "APP", "ADMIN", "CONNECTOR")
        }
        env_file.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    values = dotenv_values(env_file)
    credentials = {}
    for source, (database, port, source_id) in SOURCES.items():
        root_password = values[f"{source.upper()}_ROOT_PASSWORD"]
        connector_password = values[f"{source.upper()}_CONNECTOR_PASSWORD"]
        if not root_password or not connector_password:
            raise SystemExit("Missing local demo credentials; initialize an empty configuration.")
        (LOCAL / f"{source}-root.cnf").write_text(
            f"[client]\nuser=root\npassword={root_password}\n", encoding="utf-8"
        )
        (LOCAL / f"{source}-reader.cnf").write_text(
            f"[client]\nuser=datapulse_reader\npassword={connector_password}\n"
            f"database={database}\n",
            encoding="utf-8",
        )
        ref = f"demo/{source}/readonly"
        credentials[ref] = {
            "source_system_id": source_id,
            "username": "datapulse_reader",
            "password": connector_password,
        }
        config = {
            "contract_version": 1,
            "source_system_id": source_id,
            "vendor": "mariadb",
            "host": "127.0.0.1",
            "port": port,
            "database": database,
            "credential_ref": ref,
            "tls_mode": "disabled_local_demo",
            "connect_timeout_seconds": 3,
            "read_timeout_seconds": 3,
        }
        (LOCAL / f"{source}.json").write_text(json.dumps(config, indent=2) + "\n")
    (LOCAL / "credentials.json").write_text(json.dumps(credentials, indent=2) + "\n")
    print("Hospital-local demo configuration ready; secret files are ignored by Git.")


def provision() -> None:
    from verify_environment import verify

    if not all(item["accepted"] for item in verify().values()):
        raise SystemExit(
            "Both pinned EHR environments must pass verification before role provisioning."
        )
    values = dotenv_values(DEMO / ".env")
    for source, (database, _, _) in SOURCES.items():
        password = values.get(f"{source.upper()}_CONNECTOR_PASSWORD", "")
        # Only generated hexadecimal credentials enter bootstrap SQL, never CLI args.
        if (
            not password
            or len(password) != 48
            or any(c not in "0123456789abcdef" for c in password)
        ):
            raise SystemExit("Provisioning requires generated demo credentials.")
        sql = (
            f"CREATE USER IF NOT EXISTS 'datapulse_reader'@'%' IDENTIFIED BY '{password}';\n"
            f"ALTER USER 'datapulse_reader'@'%' IDENTIFIED BY '{password}';\n"
            "REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'datapulse_reader'@'%';\n"
            f"GRANT SELECT ON `{database}`.* TO 'datapulse_reader'@'%';\n"
        )
        result = compose(
            "exec",
            "-T",
            f"{source}-db",
            "mariadb",
            "--defaults-extra-file=/run/datapulse/root.cnf",
            input_text=sql,
        )
        if result.returncode:
            raise SystemExit(f"{source}: role provisioning failed (details suppressed).")
        print(f"{source}: separate SELECT-only connector identity provisioned.")


def reset() -> None:
    # Compose owns deletion: fixed project/file, no global prune or computed shell paths.
    result = compose("down", "--volumes", "--remove-orphans")
    if result.returncode:
        raise SystemExit("Dedicated demo reset failed (details suppressed).")
    print("Only datapulse-m3-demo fictional EHR volumes removed. Credentials retained.")


def repair_unknown_provider() -> bool:
    """Narrow pinned EMR API bootstrap repair; existing metadata only, never patients."""
    from verify_environment import query

    identity = "f9badd80-ab76-11e2-9e96-0800200c9a66"
    state = query(
        "openmrs",
        "SELECT (SELECT COUNT(*) FROM openmrs.provider "
        f"WHERE uuid='{identity}' AND retired=0), "
        "(SELECT COUNT(*) FROM openmrs.global_property "
        "WHERE property='provider.unknownProviderUuid'), "
        "(SELECT COUNT(*) FROM openmrs.global_property "
        f"WHERE property='provider.unknownProviderUuid' AND property_value='{identity}');",
    )
    if state == "1\t1\t1":
        return True
    if state != "1\t1\t0":
        return False
    unset = query(
        "openmrs",
        "SELECT COUNT(*) FROM openmrs.global_property "
        "WHERE property='provider.unknownProviderUuid' AND "
        "(property_value IS NULL OR property_value='' OR property_value='null');",
    )
    if unset != "1":
        return False
    result = query(
        "openmrs",
        "UPDATE openmrs.global_property "
        f"SET property_value='{identity}' WHERE property='provider.unknownProviderUuid' "
        "AND (property_value IS NULL OR property_value='' OR property_value='null'); "
        "SELECT ROW_COUNT();",
    )
    return result == "1"


def wait_for_installers() -> None:
    from verify_environment import verify

    container = compose("ps", "--quiet", "openmrs").stdout.strip()
    if not container or any(c not in "0123456789abcdef" for c in container):
        raise SystemExit("OpenMRS container unavailable.")
    inspected = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.StartedAt}}", container],
        capture_output=True,
        text=True,
        check=False,
    )
    since = inspected.stdout.strip()
    if inspected.returncode or not since:
        raise SystemExit("OpenMRS startup metadata unavailable.")
    started = time.monotonic()
    restarted = False
    repaired_provider = False
    last_update = started - 60
    while time.monotonic() - started < 900:
        state = verify()
        if all(item["accepted"] for item in state.values()):
            print(
                "Both pinned EHR environments accepted (versions, baseline, application readiness)."
            )
            return
        openmrs = state["openmrs"]
        if (
            not repaired_provider
            and openmrs["pinned_metadata_matches"]
            and str(openmrs.get("database_version", "")).startswith("10.11.7")
            and not openmrs["application_ready"]
        ):
            logs = compose("logs", "--since", since, "--tail", "2000", "openmrs")
            if (
                "f9badd80-ab76-11e2-9e96-0800200c9a66" in logs.stdout
                and "Duplicate entry" in logs.stdout
            ):
                if not repair_unknown_provider():
                    raise SystemExit(
                        "Unrecognized OpenMRS provider bootstrap metadata; recovery refused."
                    )
                if compose("restart", "openmrs").returncode:
                    raise SystemExit("OpenMRS provider bootstrap restart failed.")
                repaired_provider = True
                restarted = True
                print("Recovered verified OpenMRS unknown-provider bootstrap metadata; restarting.")
        if (
            not restarted
            and openmrs["pinned_metadata_matches"]
            and not openmrs["application_ready"]
        ):
            logs = compose("logs", "--since", since, "--tail", "500", "openmrs")
            if (
                "Done refreshing Context" in logs.stdout
                and "Filters cannot be added to context" in logs.stdout
            ):
                result = compose("restart", "openmrs")
                if result.returncode:
                    raise SystemExit("OpenMRS post-install restart failed.")
                restarted = True
                print("OpenMRS first installation completed; performing required servlet restart.")
        if time.monotonic() - last_update >= 60:
            print("Waiting for pinned EHR installer acceptance.")
            last_update = time.monotonic()
        time.sleep(5)
    raise SystemExit("EHR installation acceptance timed out; inspect sanitized startup metadata.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("init", "up", "wait", "provision", "stop", "reset", "status")
    )
    args = parser.parse_args()
    if args.action == "init":
        initialize()
        return
    if not (DEMO / ".env").exists():
        raise SystemExit("Run init first.")
    if args.action == "wait":
        wait_for_installers()
    elif args.action == "provision":
        provision()
    elif args.action == "reset":
        reset()
    else:
        commands = {"up": ("up", "-d"), "stop": ("stop",), "status": ("ps",)}
        result = compose(*commands[args.action])
        if result.returncode:
            print("Demo operation failed; inspect sanitized service status.", file=sys.stderr)
            raise SystemExit(1)
        print(result.stdout if args.action == "status" else f"Demo {args.action} completed.")


if __name__ == "__main__":
    # Docker Desktop's Windows helper must be reachable without machine-level changes.
    helper = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/DockerDesktop/resources/bin"
    if helper.exists():
        os.environ["PATH"] = str(helper) + os.pathsep + os.environ["PATH"]
    main()
