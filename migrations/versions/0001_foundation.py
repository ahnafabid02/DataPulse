"""Organization and source deployment foundation; no clinical/identity tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_organizations_code"),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_organizations_code"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name"),
    )
    op.create_table(
        "source_systems",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("ehr_product", sa.String(100), nullable=False),
        sa.Column("ehr_version", sa.String(100), nullable=True),
        sa.Column("database_vendor", sa.String(30), nullable=False),
        sa.Column("database_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), server_default="registered", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", "code", name="uq_source_systems_org_code"),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_source_systems_code"),
        sa.CheckConstraint("length(trim(ehr_product)) > 0", name="ck_source_systems_ehr_product"),
        sa.CheckConstraint(
            "length(trim(database_name)) > 0", name="ck_source_systems_database_name"
        ),
        sa.CheckConstraint(
            "database_vendor IN ('postgresql','mysql','mariadb','sqlserver','oracle')",
            name="ck_source_systems_vendor",
        ),
        sa.CheckConstraint(
            "status IN ('registered','active','suspended')", name="ck_source_systems_status"
        ),
    )
    op.create_index("ix_source_systems_organization_id", "source_systems", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_source_systems_organization_id", table_name="source_systems")
    op.drop_table("source_systems")
    op.drop_table("organizations")
