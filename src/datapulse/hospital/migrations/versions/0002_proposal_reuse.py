"""Index exact proposal inputs without confusing reuse with approval."""

import sqlalchemy as sa
from alembic import op

revision = "hospital_0002"
down_revision = "hospital_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mapping_runs", sa.Column("reuse_key", sa.String(64), nullable=True))
    op.create_index("ix_run_reuse", "mapping_runs", ["source_id", "reuse_key"])


def downgrade() -> None:
    op.drop_index("ix_run_reuse", table_name="mapping_runs")
    op.drop_column("mapping_runs", "reuse_key")
