"""Central registration, scoped access and append-only audit persistence through M2."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("code", name="uq_organizations_code"),
        CheckConstraint("length(trim(code)) > 0", name="ck_organizations_code"),
        CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SourceSystem(Base):
    __tablename__ = "source_systems"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_source_systems_org_code"),
        CheckConstraint("length(trim(code)) > 0", name="ck_source_systems_code"),
        CheckConstraint("length(trim(ehr_product)) > 0", name="ck_source_systems_ehr_product"),
        CheckConstraint("length(trim(database_name)) > 0", name="ck_source_systems_database_name"),
        CheckConstraint(
            "database_vendor IN ('postgresql','mysql','mariadb','sqlserver','oracle')",
            name="ck_source_systems_vendor",
        ),
        CheckConstraint(
            "status IN ('registered','active','suspended')", name="ck_source_systems_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(100))
    ehr_product: Mapped[str] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ehr_version: Mapped[str | None] = mapped_column(String(100))
    database_vendor: Mapped[str] = mapped_column(String(30))
    database_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(30), default="registered", server_default="registered"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Principal(Base):
    __tablename__ = "principals"
    __table_args__ = (
        CheckConstraint("kind IN ('human','connector')", name="ck_principals_kind"),
        CheckConstraint(
            "(kind = 'human' AND username IS NOT NULL AND password_hash IS NOT NULL "
            "AND source_system_id IS NULL) OR (kind = 'connector' AND username IS NULL "
            "AND password_hash IS NULL AND source_system_id IS NOT NULL)",
            name="ck_principals_binding",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    username: Mapped[str | None] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    source_system_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_systems.id", ondelete="RESTRICT"), unique=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RoleGrant(Base):
    __tablename__ = "role_grants"
    principal_id: Mapped[UUID] = mapped_column(
        ForeignKey("principals.id", ondelete="RESTRICT"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(50), primary_key=True)


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (
        CheckConstraint("kind IN ('session','connector')", name="ck_credentials_kind"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    principal_id: Mapped[UUID] = mapped_column(
        ForeignKey("principals.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("principals.id", ondelete="RESTRICT"))
    actor_kind: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[UUID | None] = mapped_column()
    source_system_id: Mapped[UUID | None] = mapped_column()
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    request_id: Mapped[str] = mapped_column(String(36))
    change_metadata: Mapped[dict[str, object]] = mapped_column(JSON)
