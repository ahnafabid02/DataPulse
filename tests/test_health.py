import json
from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from datapulse.central.app import create_app
from datapulse.central.config import Settings
from datapulse.central.db import database_ready


def client_for(engine):
    settings = Settings(database_url=SecretStr("postgresql+psycopg://demo:test@localhost/test"))
    return TestClient(create_app(settings, engine=engine))


def test_liveness_independent_of_database_and_revision(empty_engine):
    with client_for(empty_engine) as client:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        UUID(response.headers["X-Request-ID"])
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}


def test_readiness_requires_current_migration(migrated_engine):
    with client_for(migrated_engine) as client:
        assert client.get("/health/ready").json() == {"status": "ready"}
        with migrated_engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = 'older_revision'"))
        assert client.get("/health/ready").status_code == 503


def test_connection_failure_is_safe(tmp_path, capsys):
    # SQLite read-only mode makes an absent database fail to open, without timing out.
    engine = create_engine(f"sqlite:///file:{tmp_path / 'missing.db'}?mode=ro&uri=true")
    try:
        assert not database_ready(engine)
        with client_for(engine) as client:
            response = client.get("/health/ready")
            assert response.status_code == 503
            assert response.json() == {"status": "not_ready"}
            assert "missing.db" not in response.text
    finally:
        engine.dispose()
    assert "missing.db" not in capsys.readouterr().out


def test_request_telemetry_does_not_log_patient_query_or_untrusted_id(empty_engine, capsys):
    with client_for(empty_engine) as client:
        response = client.get(
            "/health/live?patient=private-patient-value",
            headers={"X-Request-ID": "untrusted-secret", "Authorization": "Bearer secret-token"},
        )
    output = capsys.readouterr().out
    entry = json.loads(output.strip())
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["status_code"] == 200
    assert entry["duration_ms"] >= 0
    for secret in ("private-patient-value", "untrusted-secret", "secret-token"):
        assert secret not in output


def test_unexpected_failure_redacted(empty_engine, capsys):
    client = client_for(empty_engine)

    @client.app.get("/test-failure")
    def failure():
        raise RuntimeError("private-patient-value")

    with client:
        response = client.get("/test-failure")
    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert "private-patient-value" not in response.text + capsys.readouterr().out


def test_openapi_contains_only_implemented_milestone_paths(empty_engine):
    with client_for(empty_engine) as client:
        schema = client.get("/openapi.json").json()
    assert {
        "/health/live",
        "/health/ready",
        "/v1/sources",
        "/v1/auth/login",
        "/v1/onboarding",
    } <= set(schema["paths"])
    assert not any(
        "patient" in path or "mapping" in path or "schema-scan" in path for path in schema["paths"]
    )
    assert schema["paths"]["/v1/sources"]["post"]["security"]
    assert "503" in schema["paths"]["/health/ready"]["get"]["responses"]
