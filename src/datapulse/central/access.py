"""Authentication primitives and role permissions, independent of HTTP handlers."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from datapulse.central.models import AuditEvent, Credential, Principal, RoleGrant

PASSWORDS = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))
# Authentication carries identity; this registry separately controls permissions.
# Future roles can gain permissions without changing credentials/session protocols.
ROLE_PERMISSIONS = {
    "platform_admin": frozenset({"administration", "audit_read"}),
    "connector": frozenset({"source_read"}),
    "mapping_reviewer": frozenset(),
    "identity_reviewer": frozenset(),
    "clinical_reader": frozenset(),
}


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(encoded: str, password: str) -> bool:
    try:
        return PASSWORDS.verify(encoded, password)
    except VerificationError:
        return False


def issue_credential(session: Session, principal: Principal, kind: str) -> tuple[Credential, str]:
    identifier = uuid4()
    token = f"dp_{identifier.hex}.{secrets.token_urlsafe(32)}"
    credential = Credential(
        id=identifier,
        principal_id=principal.id,
        kind=kind,
        token_hash=digest(token),
        expires_at=datetime.now(UTC)
        + (timedelta(hours=8) if kind == "session" else timedelta(days=90)),
    )
    session.add(credential)
    session.flush()
    return credential, token


def roles_for(session: Session, principal: Principal) -> list[str]:
    return list(
        session.scalars(select(RoleGrant.role).where(RoleGrant.principal_id == principal.id))
    )


def permits(session: Session, principal: Principal, permission: str) -> bool:
    return any(
        permission in ROLE_PERMISSIONS.get(role, frozenset())
        for role in roles_for(session, principal)
    )


def revoke_credentials(session: Session, principal_id: UUID) -> None:
    session.execute(
        update(Credential)
        .where(Credential.principal_id == principal_id, Credential.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def audit(
    session: Session,
    actor: Principal | None,
    action: str,
    target_type: str,
    target_id: UUID | None,
    request_id: str,
    metadata: dict[str, object] | None = None,
    source_id: UUID | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_id=actor.id if actor else None,
            actor_kind=actor.kind
            if actor
            else ("unauthenticated" if action.startswith("security.request_") else "operator"),
            action=action,
            target_type=target_type,
            target_id=target_id,
            source_system_id=source_id,
            request_id=request_id,
            change_metadata=metadata or {},
        )
    )


def initialize_admin(
    session: Session, username: str, password: str, *, reset: bool = False
) -> Principal:
    """Operator-only bootstrap/recovery. No public registration or default password."""
    if not username.strip() or len(username) > 100 or not 12 <= len(password) <= 128:
        raise ValueError("Use a username and a password of 12–128 characters.")
    # Table lock serializes first-admin bootstrap across processes on PostgreSQL.
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.connection().exec_driver_sql("LOCK TABLE principals IN EXCLUSIVE MODE")
    existing = session.scalar(select(Principal).where(Principal.kind == "human"))
    if existing:
        if not reset or existing.username != username:
            raise ValueError("An administrator already exists. Use reset with its username.")
        existing.password_hash = PASSWORDS.hash(password)
        existing.failed_logins = 0
        existing.locked_until = None
        revoke_credentials(session, existing.id)
        principal = existing
    else:
        principal = Principal(
            kind="human", username=username, password_hash=PASSWORDS.hash(password)
        )
        session.add(principal)
        session.flush()
        session.add(RoleGrant(principal_id=principal.id, role="platform_admin"))
    audit(
        session,
        None,
        "admin.password_reset" if existing else "admin.created",
        "principal",
        principal.id,
        str(uuid4()),
        {"method": "local_operator"},
    )
    return principal
