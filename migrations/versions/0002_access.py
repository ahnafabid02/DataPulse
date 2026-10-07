"""Scoped principals, revocable credentials, registration revisions and immutable audit."""

import sqlalchemy as sa
from alembic import op

revision = "0002_access"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("organizations", "source_systems"):
        op.add_column(
            table, sa.Column("revision", sa.Integer(), server_default="1", nullable=False)
        )
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "principals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("username", sa.String(100), unique=True),
        sa.Column("password_hash", sa.String(255)),
        sa.Column(
            "source_system_id",
            sa.Uuid(),
            sa.ForeignKey("source_systems.id", ondelete="RESTRICT"),
            unique=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("failed_logins", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('human','connector')", name="ck_principals_kind"),
        sa.CheckConstraint(
            "(kind = 'human' AND username IS NOT NULL AND password_hash IS NOT NULL "
            "AND source_system_id IS NULL) OR (kind = 'connector' AND username IS NULL "
            "AND password_hash IS NULL AND source_system_id IS NOT NULL)",
            name="ck_principals_binding",
        ),
    )
    op.create_table(
        "role_grants",
        sa.Column(
            "principal_id",
            sa.Uuid(),
            sa.ForeignKey("principals.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(50), primary_key=True),
    )
    op.create_table(
        "credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "principal_id",
            sa.Uuid(),
            sa.ForeignKey("principals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('session','connector')", name="ck_credentials_kind"),
    )
    op.create_index("ix_credentials_principal_id", "credentials", ["principal_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("principals.id", ondelete="RESTRICT")),
        sa.Column("actor_kind", sa.String(30), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("target_id", sa.Uuid()),
        sa.Column("source_system_id", sa.Uuid()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("change_metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    # Database enforcement also covers direct SQL and accidental future repository writes.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION datapulse_audit_immutable() RETURNS trigger
          LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'Audit records are append-only';
          END $$""")
        op.execute("""CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit_events
          FOR EACH ROW EXECUTE FUNCTION datapulse_audit_immutable()""")
        op.execute("""CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit_events
          FOR EACH STATEMENT EXECUTE FUNCTION datapulse_audit_immutable()""")
    else:
        for operation in ("UPDATE", "DELETE"):
            op.execute(f"""CREATE TRIGGER audit_no_{operation.lower()} BEFORE {operation}
              ON audit_events BEGIN SELECT RAISE(ABORT, 'Audit records are append-only'); END""")


def downgrade() -> None:
    op.drop_table("audit_events")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION datapulse_audit_immutable()")
    op.drop_table("credentials")
    op.drop_table("role_grants")
    op.drop_table("principals")
    for table in ("source_systems", "organizations"):
        op.drop_column(table, "deleted_at")
        op.drop_column(table, "revision")
