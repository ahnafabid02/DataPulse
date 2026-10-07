from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session
from test_health import client_for

from datapulse.central.access import initialize_admin, verify_password
from datapulse.central.models import AuditEvent, Credential, Organization, Principal, RoleGrant

HEADERS = {"X-DataPulse-Request": "1"}
PASSWORD = "fictional-test-password-only"


def admin_setup(engine):
    with Session(engine) as session, session.begin():
        initialize_admin(session, "demo-admin", PASSWORD)


def signin(client):
    response = client.post(
        "/v1/auth/login", json={"username": "demo-admin", "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    return response.json()


def onboard(client, code="demo-a", source_code="primary"):
    return client.post(
        "/v1/onboarding",
        json={
            "organization": {"code": code, "name": "Fictional Hospital"},
            "source": {
                "code": source_code,
                "ehr_product": "Demo EHR",
                "ehr_version": "test-1",
                "database_vendor": "mysql",
                "database_name": "fictional_demo",
            },
        },
        headers=HEADERS,
    )


def exercise_onboarding_security(engine):
    """Run the same persistent API boundary checks on SQLite and real PostgreSQL."""
    admin_setup(engine)
    with client_for(engine) as client:
        assert client.get("/v1/sources").status_code == 401
        actor = signin(client)
        first = onboard(client)
        assert first.status_code == 201, first.text
        first = first.json()
        second = onboard(client, "demo-b").json()
        sid = first["source"]["id"]
        token = first["credential"]["token"]
        assert token.startswith("dp_") and len(token) > 70 and token != "**********"
        assert client.get("/v1/sources").json()["items"]
        assert token not in client.get("/v1/sources").text
        assert onboard(client).status_code == 409
        # Duplicate source must roll back the new hospital and its audit event as well.
        duplicate = client.post(
            "/v1/onboarding",
            json={
                "organization_id": first["organization"]["id"],
                "source": {
                    "code": "primary",
                    "ehr_product": "Demo",
                    "database_vendor": "mysql",
                    "database_name": "demo",
                },
            },
            headers=HEADERS,
        )
        assert duplicate.status_code == 409
        assert len(client.get("/v1/sources").json()["items"]) == 2
        forged = client.post(
            "/v1/sources", json={"password": "do-not-echo-secret"}, headers=HEADERS
        )
        assert forged.status_code == 422
        assert "do-not-echo-secret" not in forged.text
        assert (
            client.post("/v1/organizations", json={"code": "forbidden", "name": "Demo"}).status_code
            == 403
        )
        assert (
            client.post(
                "/v1/organizations",
                json={"code": "forbidden", "name": "Demo"},
                headers={**HEADERS, "Origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
        # A bearer token overrides any administrator cookie and cannot escalate.
        connector = {"Authorization": f"Bearer {token}"}
        assert client.get(f"/v1/sources/{sid}", headers=connector).status_code == 200
        assert (
            client.get(f"/v1/sources/{second['source']['id']}", headers=connector).status_code
            == 403
        )
        assert client.get("/v1/organizations", headers=connector).status_code == 403
        assert client.get("/v1/audit-events", headers=connector).status_code == 403
        assert (
            client.post(
                "/v1/organizations", json={"code": "attack", "name": "Demo"}, headers=connector
            ).status_code
            == 403
        )
        rotation = client.post(f"/v1/sources/{sid}/credential", headers=HEADERS)
        assert rotation.status_code == 200
        replacement = rotation.json()["token"]
        assert client.get(f"/v1/sources/{sid}", headers=connector).status_code == 401
        assert (
            client.get(
                f"/v1/sources/{sid}", headers={"Authorization": f"Bearer {replacement}"}
            ).status_code
            == 200
        )
        events = client.get("/v1/audit-events?limit=200").json()["items"]
        assert token not in str(events) and replacement not in str(events)
        assert any(
            event["actor_id"] == actor["id"] and event["action"] == "source.created"
            for event in events
        )
        assert all(
            event["occurred_at"] and event["request_id"] and "change_metadata" in event
            for event in events
        )
        assert client.post("/v1/auth/logout", headers=HEADERS).status_code == 204
        assert client.get("/v1/sources").status_code == 401
    # New application/client uses the same database; no browser state supplies registrations.
    with client_for(engine) as restarted:
        signin(restarted)
        assert len(restarted.get("/v1/sources").json()["items"]) == 2
    with Session(engine) as session:
        principal = session.scalar(select(Principal).where(Principal.username == "demo-admin"))
        assert principal.password_hash.startswith("$argon2id$")
        assert verify_password(principal.password_hash, PASSWORD)
        assert PASSWORD not in principal.password_hash
        for credential in session.scalars(select(Credential)):
            assert len(credential.token_hash) == 64 and "dp_" not in credential.token_hash


def test_onboarding_scope_rotation_audit_and_restart(migrated_engine):
    exercise_onboarding_security(migrated_engine)


def test_registration_lifecycle_and_stale_updates(migrated_engine):
    exercise_registration_lifecycle(migrated_engine)


def exercise_registration_lifecycle(engine, setup=True):
    if setup:
        admin_setup(engine)
    with client_for(engine) as client:
        signin(client)
        saved = onboard(client, "lifecycle-demo").json()
        sid, oid = saved["source"]["id"], saved["organization"]["id"]
        update_body = {
            "expected_revision": 1,
            "ehr_product": "Updated Demo",
            "ehr_version": None,
            "database_vendor": "postgresql",
            "database_name": "demo",
            "status": "suspended",
        }
        assert (
            client.patch(f"/v1/sources/{sid}", json=update_body, headers=HEADERS).status_code == 200
        )
        assert (
            client.patch(f"/v1/sources/{sid}", json=update_body, headers=HEADERS).status_code == 409
        )
        token_headers = {"Authorization": f"Bearer {saved['credential']['token']}"}
        assert client.get(f"/v1/sources/{sid}", headers=token_headers).status_code == 401
        assert client.post(f"/v1/sources/{sid}/credential", headers=HEADERS).status_code == 409
        assert (
            client.delete(
                f"/v1/organizations/{oid}?expected_revision=1", headers=HEADERS
            ).status_code
            == 409
        )
        assert (
            client.delete(f"/v1/sources/{sid}?expected_revision=2", headers=HEADERS).status_code
            == 204
        )
        assert client.get(f"/v1/sources/{sid}").status_code == 404
        assert all(item["id"] != sid for item in client.get("/v1/sources").json()["items"])
        assert (
            client.patch(
                f"/v1/organizations/{oid}",
                json={"expected_revision": 1, "name": "Renamed Demo"},
                headers=HEADERS,
            ).status_code
            == 200
        )
        assert (
            client.delete(
                f"/v1/organizations/{oid}?expected_revision=2", headers=HEADERS
            ).status_code
            == 204
        )
        actions = {
            event["action"] for event in client.get("/v1/audit-events?limit=200").json()["items"]
        }
        assert {
            "organization.updated",
            "source.updated",
            "source.retired",
            "organization.retired",
        } <= actions


def test_audit_is_append_only_even_via_direct_sql(migrated_engine):
    admin_setup(migrated_engine)
    exercise_audit_immutability(migrated_engine)


def exercise_audit_immutability(engine):
    for statement in [update(AuditEvent).values(action="tampered"), delete(AuditEvent)]:
        with Session(engine) as session:
            with pytest.raises(DatabaseError):
                session.execute(statement)
                session.commit()
            session.rollback()


def test_expiry_password_change_and_recovery_revoke_sessions(migrated_engine):
    admin_setup(migrated_engine)
    with client_for(migrated_engine) as client:
        signin(client)
        with Session(migrated_engine) as session, session.begin():
            session.execute(
                update(Credential).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        assert client.get("/v1/auth/me").status_code == 401
        signin(client)
        assert (
            client.post(
                "/v1/auth/password",
                json={"current_password": PASSWORD, "new_password": "a-new-fictional-password"},
                headers=HEADERS,
            ).status_code
            == 204
        )
        assert client.get("/v1/auth/me").status_code == 401
        assert (
            client.post(
                "/v1/auth/login",
                json={"username": "demo-admin", "password": PASSWORD},
                headers=HEADERS,
            ).status_code
            == 401
        )
        with Session(migrated_engine) as session, session.begin():
            initialize_admin(session, "demo-admin", PASSWORD, reset=True)
        signin(client)
        with Session(migrated_engine) as session, session.begin():
            initialize_admin(session, "demo-admin", PASSWORD, reset=True)
        assert client.get("/v1/auth/me").status_code == 401


def test_login_lockout_and_secret_redaction(migrated_engine, capsys):
    admin_setup(migrated_engine)
    with client_for(migrated_engine) as client:
        for _ in range(5):
            assert (
                client.post(
                    "/v1/auth/login",
                    json={"username": "demo-admin", "password": "wrong-secret-value"},
                    headers=HEADERS,
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/v1/auth/login",
                json={"username": "demo-admin", "password": PASSWORD},
                headers=HEADERS,
            ).status_code
            == 429
        )
        response = client.post(
            "/v1/auth/login",
            json={
                "username": "demo-admin",
                "password": "private-value",
                "token": "another-private-value",
            },
            headers=HEADERS,
        )
        assert response.status_code == 422
        assert "private-value" not in response.text
        response = client.post("/v1/auth/login", content=b"x" * 65537, headers=HEADERS)
        assert response.status_code == 413
    logs = capsys.readouterr().out
    assert PASSWORD not in logs and "wrong-secret-value" not in logs and "private-value" not in logs


def test_pagination_and_reserved_roles_do_not_gain_admin_access(migrated_engine):
    admin_setup(migrated_engine)
    with client_for(migrated_engine) as client:
        identity = signin(client)
        onboard(client, "first")
        onboard(client, "second")
        page = client.get("/v1/organizations?limit=1").json()
        other = client.get(f"/v1/organizations?limit=1&cursor={page['next_cursor']}").json()
        assert len(page["items"]) == len(other["items"]) == 1
        assert page["items"][0]["id"] != other["items"][0]["id"]
        assert other["next_cursor"] is None
        with Session(migrated_engine) as session, session.begin():
            session.execute(delete(RoleGrant).where(RoleGrant.principal_id == UUID(identity["id"])))
            session.add(RoleGrant(principal_id=UUID(identity["id"]), role="identity_reviewer"))
        assert client.get("/v1/auth/me").json()["roles"] == ["identity_reviewer"]
        assert client.get("/v1/sources").status_code == 403


def test_duplicate_bootstrap_is_refused(migrated_engine):
    admin_setup(migrated_engine)
    with Session(migrated_engine) as session, pytest.raises(ValueError):
        initialize_admin(session, "another-admin", PASSWORD)
    with Session(migrated_engine) as session:
        assert session.scalar(select(Organization)) is None
