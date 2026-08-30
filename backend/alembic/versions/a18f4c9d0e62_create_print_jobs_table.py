"""create print jobs table

Revision ID: a18f4c9d0e62
Revises: f7df48676562
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a18f4c9d0e62"
down_revision: Union[str, Sequence[str], None] = "f7df48676562"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "print_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("spool_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PLANNED", nullable=False),
        sa.Column("estimated_weight_g", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("actual_weight_g", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("estimated_time_minutes", sa.Integer(), nullable=True),
        sa.Column("actual_time_minutes", sa.Integer(), nullable=True),
        sa.Column("printer_name", sa.String(length=200), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.CheckConstraint("estimated_weight_g IS NULL OR estimated_weight_g > 0", name="ck_print_jobs_estimated_weight_positive"),
        sa.CheckConstraint("trim(name) <> ''", name="ck_print_jobs_name_not_blank"),
        sa.CheckConstraint("actual_weight_g IS NULL OR actual_weight_g >= 0", name="ck_print_jobs_actual_weight_non_negative"),
        sa.CheckConstraint("estimated_time_minutes IS NULL OR estimated_time_minutes > 0", name="ck_print_jobs_estimated_time_positive"),
        sa.CheckConstraint("actual_time_minutes IS NULL OR actual_time_minutes >= 0", name="ck_print_jobs_actual_time_non_negative"),
        sa.CheckConstraint("finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at", name="ck_print_jobs_timestamp_order"),
        sa.CheckConstraint("status IN ('PLANNED', 'PRINTING', 'SUCCESS', 'FAILED', 'CANCELLED')", name="ck_print_jobs_status"),
        sa.ForeignKeyConstraint(["spool_id"], ["spools.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_print_jobs_spool_id", "print_jobs", ["spool_id"], unique=False)
    op.create_index("ix_print_jobs_status", "print_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_print_jobs_status", table_name="print_jobs")
    op.drop_index("ix_print_jobs_spool_id", table_name="print_jobs")
    op.drop_table("print_jobs")
