"""Only organization/source registration persistence is part of M1."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
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
    ehr_version: Mapped[str | None] = mapped_column(String(100))
    database_vendor: Mapped[str] = mapped_column(String(30))
    database_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(30), default="registered", server_default="registered"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
