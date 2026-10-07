import pytest
from conftest import migrate
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from test_access import HEADERS, admin_setup, onboard, signin
from test_health import client_for

from datapulse.central.models import AuditEvent, Credential, Organization, SourceSystem


def test_upgrade_preserves_existing_registrations(empty_engine):
    migrate(empty_engine, "0001_foundation")
    # Use SQL against the historic contract: the current ORM already has new columns.
    with empty_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organizations (id, code, name, created_at) "
                "VALUES (:id, 'old-demo', 'Existing Demo', CURRENT_TIMESTAMP)"
            ),
            {"id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
        )
    migrate(empty_engine)
    with Session(empty_engine) as session:
        item = session.scalar(select(Organization))
        assert item.name == "Existing Demo" and item.revision == 1 and item.deleted_at is None


def test_failed_audit_rolls_back_registration(migrated_engine):
    admin_setup(migrated_engine)
    with client_for(migrated_engine) as client:
        signin(client)
        with migrated_engine.begin() as connection:
            connection.exec_driver_sql("""CREATE TRIGGER test_audit_failure
              BEFORE INSERT ON audit_events WHEN NEW.action = 'source.created'
              BEGIN SELECT RAISE(ABORT, 'simulated audit failure'); END""")
        response = onboard(client)
        assert response.status_code == 503
        with Session(migrated_engine) as session:
            assert session.scalar(select(Organization)) is None
            assert session.scalar(select(SourceSystem)) is None
            assert (
                session.scalar(
                    select(AuditEvent).where(AuditEvent.action == "organization.created")
                )
                is None
            )


def test_revoke_and_expired_connector_deny_access(migrated_engine):
    admin_setup(migrated_engine)
    with client_for(migrated_engine) as client:
        signin(client)
        saved = onboard(client).json()
        sid = saved["source"]["id"]
        headers = {"Authorization": f"Bearer {saved['credential']['token']}"}
        assert client.delete(f"/v1/sources/{sid}/credential", headers=HEADERS).status_code == 204
        assert client.get(f"/v1/sources/{sid}", headers=headers).status_code == 401
        replacement = client.post(f"/v1/sources/{sid}/credential", headers=HEADERS).json()
        with Session(migrated_engine) as session, session.begin():
            from datetime import UTC, datetime, timedelta
            from uuid import UUID

            item = session.get(Credential, UUID(replacement["id"]))
            item.expires_at = datetime.now(UTC) - timedelta(days=1)
        assert (
            client.get(
                f"/v1/sources/{sid}", headers={"Authorization": f"Bearer {replacement['token']}"}
            ).status_code
            == 401
        )


@pytest.mark.parametrize(
    "database_name", ["mysql://user:secret@host/db", "user=demo password=secret", "https://host"]
)
def test_connection_strings_are_rejected(migrated_engine, database_name):
    admin_setup(migrated_engine)
    with client_for(migrated_engine) as client:
        signin(client)
        response = client.post(
            "/v1/onboarding",
            json={
                "organization": {"code": "demo", "name": "Fictional Hospital"},
                "source": {
                    "code": "primary",
                    "ehr_product": "Demo",
                    "database_vendor": "mysql",
                    "database_name": database_name,
                },
            },
            headers=HEADERS,
        )
        assert response.status_code == 422
        assert database_name not in response.text
        assert client.get("/v1/organizations").json()["items"] == []


def test_audit_cursor_is_chronological_and_does_not_repeat(migrated_engine):
    admin_setup(migrated_engine)
    with client_for(migrated_engine) as client:
        signin(client)
        onboard(client)
        first = client.get("/v1/audit-events?limit=2").json()
        second = client.get(f"/v1/audit-events?limit=2&cursor={first['next_cursor']}").json()
        assert not ({e["id"] for e in first["items"]} & {e["id"] for e in second["items"]})
        assert first["items"][-1]["occurred_at"] >= second["items"][0]["occurred_at"]


def test_human_and_connector_credentials_cannot_switch_transport(migrated_engine):
    admin_setup(migrated_engine)
    with client_for(migrated_engine) as client:
        signin(client)
        saved = onboard(client).json()
        human_token = client.cookies.get("datapulse_session")
        assert (
            client.get(
                "/v1/auth/me", headers={"Authorization": f"Bearer {human_token}"}
            ).status_code
            == 401
        )
        client.cookies.clear()
        client.cookies.set("datapulse_session", saved["credential"]["token"], path="/v1")
        assert client.get("/v1/auth/me").status_code == 401


def test_documentation_assets_and_workspace_have_distinct_csp(migrated_engine):
    with client_for(migrated_engine) as client:
        docs_policy = client.get("/docs").headers["content-security-policy"]
        assert "https://cdn.jsdelivr.net" in docs_policy
        assert "unsafe-inline" not in client.get("/health/live").headers["content-security-policy"]
