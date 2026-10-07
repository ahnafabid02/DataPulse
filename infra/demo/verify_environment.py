"""Check known pinned installer metadata, never discover schemas or read patient bodies."""

import base64
import http.client
import json
import urllib.error
import urllib.request

from demo import DEMO, SOURCES, compose
from dotenv import dotenv_values


def query(source: str, sql: str) -> str | None:
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
    return result.stdout.strip() if result.returncode == 0 else None


def verify() -> dict[str, object]:
    secrets = dotenv_values(DEMO / ".env")
    result: dict[str, object] = {}
    for source in SOURCES:
        version = query(source, "SELECT VERSION();")
        if source == "openmrs":
            counts = query(
                source,
                "SELECT (SELECT COUNT(*) FROM openmrs.patient), "
                "(SELECT COUNT(*) FROM openmrs.encounter), (SELECT COUNT(*) FROM openmrs.obs);",
            )
            expected_db = "10.11.7"
            url = "http://127.0.0.1:8081/openmrs/ws/rest/v1/session"
            password = secrets["OPENMRS_ADMIN_PASSWORD"]
            authorization = base64.b64encode(f"admin:{password}".encode()).decode()
            request = urllib.request.Request(
                url, headers={"Authorization": f"Basic {authorization}"}
            )
            app_version_result = compose(
                "exec",
                "-T",
                "openmrs",
                "bash",
                "-c",
                "find /usr/local/tomcat/webapps/openmrs/WEB-INF/lib -maxdepth 1 "
                "-name 'openmrs-api-*.jar' -printf '%f\\n'",
            )
            app_version = app_version_result.stdout.strip()
            seed_result = compose(
                "exec",
                "-T",
                "openmrs",
                "bash",
                "-c",
                "grep -cx 'referencedemodata.createDemoPatients=false' "
                "/openmrs/data/openmrs-runtime.properties",
            )
            seed_flag = seed_result.returncode == 0
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    app_ready = json.load(response).get("authenticated") is True
            except (OSError, urllib.error.URLError, http.client.HTTPException, ValueError):
                app_ready = False
            metadata_ready = app_version == "openmrs-api-2.8.8.jar" and seed_flag
        else:
            expected_db = "12.3.3"
            counts = query(source, "SELECT COUNT(*) FROM openemr.patient_data;")
            app_version_result = compose(
                "exec",
                "-T",
                "openemr",
                "php",
                "-r",
                "require '/var/www/localhost/htdocs/openemr/version.php'; "
                "echo $v_major.'.'.$v_minor.'.'.$v_patch.'|'.$v_database;",
            )
            app_version = app_version_result.stdout.strip()
            request = urllib.request.Request("http://127.0.0.1:8082/meta/health/readyz")
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    app_ready = response.status == 200
            except (OSError, urllib.error.URLError, http.client.HTTPException):
                app_ready = False
            schema_version = query(
                source, "SELECT v_major,v_minor,v_patch,v_database FROM openemr.version;"
            )
            metadata_ready = app_version == "8.4.1|543" and schema_version == "8\t4\t1\t543"
        empty = counts is not None and all(int(value) == 0 for value in counts.split())
        seeded = False
        if not empty and counts is not None and metadata_ready:
            from seed_clinical import verify_seed

            try:
                seeded = verify_seed(source)
            except Exception:
                seeded = False
        result[source] = {
            "database_version": version,
            "application_version": app_version,
            "application_ready": app_ready,
            "empty_clinical_baseline": empty,
            "recognized_fictional_seed": seeded,
            "pinned_metadata_matches": metadata_ready,
            "accepted": bool(
                version
                and version.startswith(expected_db)
                and metadata_ready
                and app_ready
                and (empty or seeded)
            ),
        }
    return result


if __name__ == "__main__":
    result = verify()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(item["accepted"] for item in result.values()) else 1)
