"""Immutable bounded evidence and metadata-only source-read audit."""

import sqlalchemy as sa
from alembic import op

revision = "hospital_0003"
down_revision = "hospital_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("access_id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("schema_scans.id"), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "evidence_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("access_id", sa.String(36), nullable=False, unique=True),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("scan_id", sa.String(36), sa.ForeignKey("schema_scans.id"), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    for table in ("evidence_access", "evidence_observations"):
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'Immutable hospital evidence'); END"
            )


def downgrade() -> None:
    for table in ("evidence_observations", "evidence_access"):
        for action in ("UPDATE", "DELETE"):
            op.execute(f"DROP TRIGGER {table}_no_{action.lower()}")
        op.drop_table(table)
