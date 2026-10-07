"""M2 registration and security API. No source database access or clinical workflows."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_serializer, model_validator
from sqlalchemy import Engine, and_, or_, select
from sqlalchemy.orm import Session

from datapulse.central.access import (
    DUMMY_HASH,
    PASSWORDS,
    audit,
    digest,
    issue_credential,
    permits,
    revoke_credentials,
    roles_for,
    utc,
    verify_password,
)
from datapulse.central.config import Settings
from datapulse.central.models import (
    AuditEvent,
    Credential,
    Organization,
    Principal,
    RoleGrant,
    SourceSystem,
)

COOKIE = "datapulse_session"
bearer = HTTPBearer(auto_error=False)
cookie = APIKeyCookie(name=COOKIE, auto_error=False)
Name = Annotated[str, Field(min_length=1, max_length=255)]
Code = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")]
Short = Annotated[str, Field(min_length=1, max_length=100)]
DatabaseLabel = Annotated[
    str, Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
]
Vendor = Literal["postgresql", "mysql", "mariadb", "sqlserver", "oracle"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)

    @field_serializer("created_at", "expires_at", "occurred_at", check_fields=False)
    def serialize_time(self, value: datetime) -> str:
        return utc(value).isoformat()


class Login(Contract):
    username: Short
    # SecretStr prevents accidental repr/logging; passwords preserve whitespace.
    password: SecretStr = Field(min_length=1, max_length=128)


class PasswordChange(Contract):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)


class Identity(Contract):
    id: UUID
    kind: str
    username: str | None
    source_system_id: UUID | None
    roles: list[str]


class OrganizationCreate(Contract):
    code: Code
    name: Name


class OrganizationView(OrganizationCreate):
    id: UUID
    revision: int
    created_at: datetime


class OrganizationUpdate(Contract):
    expected_revision: int = Field(ge=1)
    name: Name


class SourceDetails(Contract):
    code: Code
    ehr_product: Short
    ehr_version: Short | None = None
    database_vendor: Vendor
    database_name: DatabaseLabel


class SourceCreate(SourceDetails):
    organization_id: UUID


class SourceView(SourceCreate):
    id: UUID
    status: str
    revision: int
    created_at: datetime


class SourceUpdate(Contract):
    expected_revision: int = Field(ge=1)
    ehr_product: Short
    ehr_version: Short | None = None
    database_vendor: Vendor
    database_name: DatabaseLabel
    status: Literal["registered", "suspended"]


class CredentialView(Contract):
    id: UUID
    token: SecretStr
    expires_at: datetime


class SourceCreated(Contract):
    source: SourceView
    credential: CredentialView


class Onboard(Contract):
    organization: OrganizationCreate | None = None
    organization_id: UUID | None = None
    source: SourceDetails

    @model_validator(mode="after")
    def one_organization(self) -> "Onboard":
        if (self.organization is None) == (self.organization_id is None):
            raise ValueError("Choose either an existing hospital or a new hospital")
        return self


class Onboarded(SourceCreated):
    organization: OrganizationView


class OrganizationPage(Contract):
    items: list[OrganizationView]
    next_cursor: UUID | None


class SourcePage(Contract):
    items: list[SourceView]
    next_cursor: UUID | None


class AuditView(Contract):
    id: UUID
    actor_id: UUID | None
    actor_kind: str
    action: str
    target_type: str
    target_id: UUID | None
    source_system_id: UUID | None
    occurred_at: datetime
    request_id: str
    change_metadata: dict[str, object]


class AuditPage(Contract):
    items: list[AuditView]
    next_cursor: UUID | None


def fail(status: int, message: str) -> NoReturn:
    raise HTTPException(status, message)


def install_api(engine: Engine, config: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["administration"])

    def database() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    DB = Annotated[Session, Depends(database)]

    def authenticated(
        request: Request,
        session: DB,
        authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        session_cookie: Annotated[str | None, Depends(cookie)],
    ) -> Principal:
        # Bearer credentials are exclusively for connectors; cookies for humans.
        token = authorization.credentials if authorization else session_cookie
        if not token or len(token) > 256:
            fail(401, "Sign in or supply a valid connector credential.")
        credential = session.scalar(
            select(Credential).where(Credential.token_hash == digest(token or ""))
        )
        if (
            not credential
            or credential.revoked_at
            or utc(credential.expires_at) <= datetime.now(UTC)
        ):
            fail(401, "Your access has expired. Sign in or renew the connector credential.")
        assert credential is not None
        expected_kind = "connector" if authorization else "session"
        if credential.kind != expected_kind:
            fail(401, "Use the correct sign-in method for this identity.")
        principal = session.get(Principal, credential.principal_id)
        if not principal or not principal.enabled:
            fail(401, "This identity no longer has access.")
        assert principal is not None
        request.state.actor_id = principal.id
        request.state.credential_id = credential.id
        if principal.kind == "connector":
            source = session.get(SourceSystem, principal.source_system_id)
            if not source or source.deleted_at or source.status == "suspended":
                fail(403, "This source system is suspended or retired.")
        elif request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("X-DataPulse-Request") != "1":
                fail(403, "Refresh the workspace and try again.")
            origin = request.headers.get("origin")
            if origin and origin != config.browser_origin:
                fail(403, "This request must come from the DataPulse workspace.")
        return principal

    Actor = Annotated[Principal, Depends(authenticated)]

    def administrator(actor: Actor, session: DB) -> Principal:
        if actor.kind != "human" or not permits(session, actor, "administration"):
            fail(403, "Only the platform administrator can manage hospital setup.")
        return actor

    Admin = Annotated[Principal, Depends(administrator)]

    def event(
        session: Session,
        request: Request,
        actor: Principal,
        action: str,
        target: Organization | SourceSystem | Principal | Credential,
        metadata: dict[str, object] | None = None,
    ) -> None:
        audit(
            session,
            actor,
            action,
            target.__tablename__,
            target.id,
            request.state.request_id,
            metadata,
            target.id if isinstance(target, SourceSystem) else actor.source_system_id,
        )

    def commit(session: Session) -> None:
        session.commit()

    def organization(session: Session, identifier: UUID, *, lock: bool = False) -> Organization:
        statement = select(Organization).where(
            Organization.id == identifier, Organization.deleted_at.is_(None)
        )
        if lock:
            statement = statement.with_for_update()
        item = session.scalar(statement)
        if not item:
            fail(404, "Hospital registration was not found.")
        assert item is not None
        return item

    def source(session: Session, identifier: UUID, *, lock: bool = False) -> SourceSystem:
        statement = select(SourceSystem).where(
            SourceSystem.id == identifier, SourceSystem.deleted_at.is_(None)
        )
        if lock:
            statement = statement.with_for_update()
        item = session.scalar(statement)
        if not item:
            fail(404, "Source registration was not found.")
        assert item is not None
        return item

    def check_revision(item: Organization | SourceSystem, expected: int) -> None:
        if item.revision != expected:
            fail(409, "These details changed. Refresh before saving again.")

    def new_organization(
        session: Session, request: Request, actor: Principal, data: OrganizationCreate
    ) -> Organization:
        item = Organization(**data.model_dump())
        session.add(item)
        session.flush()
        event(session, request, actor, "organization.created", item, {"after": data.model_dump()})
        return item

    def credential_view(credential: Credential, token: str) -> CredentialView:
        # SecretStr normally redacts JSON. One-time disclosure is explicit here.
        return CredentialView(
            id=credential.id, token=SecretStr(token), expires_at=utc(credential.expires_at)
        )

    def new_source(
        session: Session, request: Request, actor: Principal, data: SourceCreate
    ) -> SourceCreated:
        organization(session, data.organization_id, lock=True)
        item = SourceSystem(**data.model_dump())
        session.add(item)
        session.flush()
        principal = Principal(kind="connector", source_system_id=item.id)
        session.add(principal)
        session.flush()
        session.add(RoleGrant(principal_id=principal.id, role="connector"))
        credential, token = issue_credential(session, principal, "connector")
        event(
            session, request, actor, "source.created", item, {"after": data.model_dump(mode="json")}
        )
        event(
            session,
            request,
            actor,
            "connector.credential_issued",
            item,
            {"credential_id": str(credential.id), "principal_id": str(principal.id)},
        )
        return SourceCreated(
            source=SourceView.model_validate(item), credential=credential_view(credential, token)
        )

    @router.post("/auth/login", response_model=Identity, tags=["authentication"])
    def login(data: Login, request: Request, response: Response, session: DB) -> Identity:
        if request.headers.get("X-DataPulse-Request") != "1" or (
            request.headers.get("origin") and request.headers["origin"] != config.browser_origin
        ):
            fail(403, "Sign in from the DataPulse workspace.")
        principal = session.scalar(
            select(Principal)
            .where(Principal.username == data.username, Principal.kind == "human")
            .with_for_update()
        )
        now = datetime.now(UTC)
        if principal and principal.locked_until and utc(principal.locked_until) > now:
            fail(429, "Too many attempts. Wait 15 minutes before trying again.")
        correct = verify_password(
            principal.password_hash if principal and principal.password_hash else DUMMY_HASH,
            data.password.get_secret_value(),
        )
        if not principal or not correct or not principal.enabled:
            if principal:
                principal.failed_logins += 1
                if principal.failed_logins >= 5:
                    principal.locked_until = now + timedelta(minutes=15)
                    principal.failed_logins = 0
                audit(
                    session,
                    principal,
                    "auth.login_failed",
                    "principal",
                    principal.id,
                    request.state.request_id,
                )
                session.commit()
            fail(401, "The username or password is incorrect.")
        principal.failed_logins = 0
        principal.locked_until = None
        credential, token = issue_credential(session, principal, "session")
        event(session, request, principal, "auth.login", credential)
        identity = Identity.model_validate(
            {
                "id": principal.id,
                "kind": principal.kind,
                "username": principal.username,
                "source_system_id": principal.source_system_id,
                "roles": roles_for(session, principal),
            }
        )
        commit(session)
        response.set_cookie(
            COOKIE,
            token,
            max_age=8 * 3600,
            httponly=True,
            secure=config.cookie_secure,
            samesite="strict",
            path="/v1",
        )
        return identity

    @router.get("/auth/me", response_model=Identity, tags=["authentication"])
    def me(actor: Actor, session: DB) -> Identity:
        return Identity(
            id=actor.id,
            kind=actor.kind,
            username=actor.username,
            source_system_id=actor.source_system_id,
            roles=roles_for(session, actor),
        )

    @router.post("/auth/logout", status_code=204, tags=["authentication"])
    def logout(request: Request, response: Response, actor: Actor, session: DB) -> None:
        if actor.kind != "human":
            fail(403, "Only browser sessions can sign out here.")
        credential = session.get(Credential, request.state.credential_id)
        assert credential is not None
        credential.revoked_at = datetime.now(UTC)
        event(session, request, actor, "auth.logout", credential)
        commit(session)
        response.delete_cookie(
            COOKIE, path="/v1", secure=config.cookie_secure, httponly=True, samesite="strict"
        )

    @router.post("/auth/password", status_code=204, tags=["authentication"])
    def password(
        data: PasswordChange, request: Request, response: Response, actor: Admin, session: DB
    ) -> None:
        principal = session.scalar(
            select(Principal).where(Principal.id == actor.id).with_for_update()
        )
        assert principal is not None
        if not verify_password(
            principal.password_hash or DUMMY_HASH, data.current_password.get_secret_value()
        ):
            fail(401, "The current password is incorrect.")
        principal.password_hash = PASSWORDS.hash(data.new_password.get_secret_value())
        revoke_credentials(session, principal.id)
        event(session, request, actor, "admin.password_changed", principal)
        commit(session)
        response.delete_cookie(COOKIE, path="/v1")

    @router.get("/organizations", response_model=OrganizationPage)
    def organizations(
        actor: Admin, session: DB, limit: int = Query(50, ge=1, le=200), cursor: UUID | None = None
    ) -> OrganizationPage:
        statement = select(Organization).where(Organization.deleted_at.is_(None))
        if cursor:
            statement = statement.where(Organization.id > cursor)
        items = list(session.scalars(statement.order_by(Organization.id).limit(limit + 1)))
        return OrganizationPage(
            items=[OrganizationView.model_validate(item) for item in items[:limit]],
            next_cursor=items[limit - 1].id if len(items) > limit else None,
        )

    @router.post("/organizations", response_model=OrganizationView, status_code=201)
    def create_organization(
        data: OrganizationCreate, request: Request, actor: Admin, session: DB
    ) -> OrganizationView:
        item = new_organization(session, request, actor, data)
        result = OrganizationView.model_validate(item)
        commit(session)
        return result

    @router.patch("/organizations/{identifier}", response_model=OrganizationView)
    def update_organization(
        identifier: UUID, data: OrganizationUpdate, request: Request, actor: Admin, session: DB
    ) -> OrganizationView:
        item = organization(session, identifier, lock=True)
        check_revision(item, data.expected_revision)
        before = {"name": item.name, "revision": item.revision}
        item.name = data.name
        item.revision += 1
        event(
            session,
            request,
            actor,
            "organization.updated",
            item,
            {"before": before, "after": {"name": item.name, "revision": item.revision}},
        )
        result = OrganizationView.model_validate(item)
        commit(session)
        return result

    @router.delete("/organizations/{identifier}", status_code=204)
    def delete_organization(
        identifier: UUID,
        request: Request,
        actor: Admin,
        session: DB,
        expected_revision: int = Query(ge=1),
    ) -> None:
        item = organization(session, identifier, lock=True)
        check_revision(item, expected_revision)
        if session.scalar(
            select(SourceSystem.id)
            .where(SourceSystem.organization_id == identifier, SourceSystem.deleted_at.is_(None))
            .limit(1)
        ):
            fail(409, "Retire this hospital’s source systems before retiring the hospital.")
        item.deleted_at = datetime.now(UTC)
        item.revision += 1
        event(session, request, actor, "organization.retired", item, {"revision": item.revision})
        commit(session)

    @router.get("/sources", response_model=SourcePage)
    def sources(
        actor: Admin, session: DB, limit: int = Query(50, ge=1, le=200), cursor: UUID | None = None
    ) -> SourcePage:
        statement = select(SourceSystem).where(SourceSystem.deleted_at.is_(None))
        if cursor:
            statement = statement.where(SourceSystem.id > cursor)
        items = list(session.scalars(statement.order_by(SourceSystem.id).limit(limit + 1)))
        return SourcePage(
            items=[SourceView.model_validate(item) for item in items[:limit]],
            next_cursor=items[limit - 1].id if len(items) > limit else None,
        )

    @router.get("/sources/{identifier}", response_model=SourceView)
    def read_source(identifier: UUID, actor: Actor, session: DB) -> SourceView:
        if not (actor.kind == "human" and permits(session, actor, "administration")):
            if not permits(session, actor, "source_read") or actor.source_system_id != identifier:
                fail(403, "This connector can only access its own registered source system.")
        return SourceView.model_validate(source(session, identifier))

    @router.post("/sources", response_model=SourceCreated, status_code=201)
    def create_source(data: SourceCreate, request: Request, actor: Admin, session: DB) -> Response:
        result = new_source(session, request, actor, data)
        commit(session)
        return disclose(result)

    @router.post("/onboarding", response_model=Onboarded, status_code=201)
    def onboarding(data: Onboard, request: Request, actor: Admin, session: DB) -> Response:
        if data.organization:
            org = new_organization(session, request, actor, data.organization)
        else:
            assert data.organization_id is not None
            org = organization(session, data.organization_id)
        created = new_source(
            session,
            request,
            actor,
            SourceCreate(organization_id=org.id, **data.source.model_dump()),
        )
        result = Onboarded(
            organization=OrganizationView.model_validate(org),
            source=created.source,
            credential=created.credential,
        )
        commit(session)
        return disclose(result)

    @router.patch("/sources/{identifier}", response_model=SourceView)
    def update_source(
        identifier: UUID, data: SourceUpdate, request: Request, actor: Admin, session: DB
    ) -> SourceView:
        item = source(session, identifier, lock=True)
        check_revision(item, data.expected_revision)
        before = SourceView.model_validate(item).model_dump(mode="json")
        for key, value in data.model_dump(exclude={"expected_revision"}).items():
            setattr(item, key, value)
        item.revision += 1
        if item.status == "suspended":
            principal = session.scalar(
                select(Principal).where(Principal.source_system_id == identifier)
            )
            if principal:
                revoke_credentials(session, principal.id)
        result = SourceView.model_validate(item)
        event(
            session,
            request,
            actor,
            "source.updated",
            item,
            {"before": before, "after": result.model_dump(mode="json")},
        )
        commit(session)
        return result

    @router.delete("/sources/{identifier}", status_code=204)
    def delete_source(
        identifier: UUID,
        request: Request,
        actor: Admin,
        session: DB,
        expected_revision: int = Query(ge=1),
    ) -> None:
        item = source(session, identifier, lock=True)
        check_revision(item, expected_revision)
        item.deleted_at = datetime.now(UTC)
        item.status = "suspended"
        item.revision += 1
        principal = session.scalar(
            select(Principal).where(Principal.source_system_id == identifier)
        )
        if principal:
            principal.enabled = False
            revoke_credentials(session, principal.id)
        event(session, request, actor, "source.retired", item, {"revision": item.revision})
        commit(session)

    @router.post(
        "/sources/{identifier}/credential", response_model=CredentialView, tags=["security"]
    )
    def rotate(identifier: UUID, request: Request, actor: Admin, session: DB) -> Response:
        item = source(session, identifier, lock=True)
        if item.status == "suspended":
            fail(409, "Resume this registration before issuing a credential.")
        principal = session.scalar(
            select(Principal).where(Principal.source_system_id == identifier)
        )
        assert principal is not None
        revoke_credentials(session, principal.id)
        credential, token = issue_credential(session, principal, "connector")
        event(
            session,
            request,
            actor,
            "connector.credential_rotated",
            item,
            {"credential_id": str(credential.id), "principal_id": str(principal.id)},
        )
        result = credential_view(credential, token)
        commit(session)
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {
                "id": str(result.id),
                "token": result.token.get_secret_value(),
                "expires_at": result.expires_at.isoformat(),
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.delete("/sources/{identifier}/credential", status_code=204, tags=["security"])
    def revoke(identifier: UUID, request: Request, actor: Admin, session: DB) -> None:
        item = source(session, identifier, lock=True)
        principal = session.scalar(
            select(Principal).where(Principal.source_system_id == identifier)
        )
        assert principal is not None
        revoke_credentials(session, principal.id)
        event(session, request, actor, "connector.credential_revoked", item)
        commit(session)

    @router.get("/audit-events", response_model=AuditPage, tags=["audit"])
    def audit_events(
        request: Request,
        actor: Admin,
        session: DB,
        limit: int = Query(50, ge=1, le=200),
        cursor: UUID | None = None,
    ) -> AuditPage:
        if not permits(session, actor, "audit_read"):
            fail(403, "Audit access is not permitted for this identity.")
        statement = select(AuditEvent)
        if cursor:
            boundary = session.get(AuditEvent, cursor)
            if not boundary:
                fail(422, "The activity cursor is invalid. Refresh the activity record.")
            statement = statement.where(
                or_(
                    AuditEvent.occurred_at < boundary.occurred_at,
                    and_(
                        AuditEvent.occurred_at == boundary.occurred_at, AuditEvent.id < boundary.id
                    ),
                )
            )
        items = list(
            session.scalars(
                statement.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(
                    limit + 1
                )
            )
        )
        result = AuditPage(
            items=[AuditView.model_validate(item) for item in items[:limit]],
            next_cursor=items[limit - 1].id if len(items) > limit else None,
        )
        audit(session, actor, "audit.read", "audit_events", None, request.state.request_id)
        commit(session)
        return result

    return router


def disclose(result: SourceCreated) -> Response:
    """The only place a freshly generated connector token leaves the server."""
    from fastapi.responses import JSONResponse

    data = result.model_dump(mode="json")
    data["credential"]["token"] = result.credential.token.get_secret_value()
    return JSONResponse(data, status_code=201, headers={"Cache-Control": "no-store"})
