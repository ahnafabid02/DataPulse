"""Immutable scans and unapproved mapping-run observations, hospital-local only."""

import sqlalchemy as sa
from alembic import op

revision = "hospital_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schema_snapshots",
        sa.Column("fingerprint", sa.String(64), primary_key=True),
        sa.Column("structure_json", sa.Text(), nullable=False),
    )
    op.create_table(
        "schema_scans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column(
            "fingerprint",
            sa.String(64),
            sa.ForeignKey("schema_snapshots.fingerprint"),
            nullable=False,
        ),
        sa.Column("scanned_at", sa.String(40), nullable=False),
        sa.Column("observation_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_scan_source", "schema_scans", ["source_id", "scanned_at"])
    op.create_table(
        "mapping_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("schema_scans.id"), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
    )
    for table in ("schema_snapshots", "schema_scans", "mapping_runs"):
        for event in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER {table}_{event.lower()} BEFORE {event} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'Immutable hospital history'); END"
            )


def downgrade() -> None:
    op.drop_table("mapping_runs")
    op.drop_table("schema_scans")
    op.drop_table("schema_snapshots")
