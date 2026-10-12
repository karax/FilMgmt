"""add persistent Bambu print history fields

Revision ID: 6c4f2a9d8e10
Revises: f2a8c7d190b4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "6c4f2a9d8e10"
down_revision: Union[str, Sequence[str], None] = "f2a8c7d190b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("print_jobs") as batch:
        batch.drop_constraint("ck_print_jobs_name_not_blank", type_="check")
        batch.drop_constraint("ck_print_jobs_status", type_="check")
        batch.alter_column("name", existing_type=sa.String(length=200), nullable=True)
        batch.add_column(sa.Column("printer_serial", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("bambu_identity_key", sa.String(length=700), nullable=True))
        batch.add_column(sa.Column("task_id", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("subtask_id", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("project_id", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("profile_id", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("gcode_file", sa.Text(), nullable=True))
        batch.add_column(sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("raw_bambu_state", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("start_progress", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("final_progress", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("start_layer", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("final_layer", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("total_layers", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("duration_seconds", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("remaining_time_minutes", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("capture_mode", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("reconciliation_status", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("ams_snapshot", sa.JSON(), nullable=True))
        batch.create_check_constraint(
            "ck_print_jobs_name_not_blank",
            "name IS NULL OR trim(name) <> ''",
        )
        batch.create_check_constraint(
            "ck_print_jobs_status",
            "status IN ('PLANNED', 'PRINTING', 'PAUSED', 'SUCCESS', 'COMPLETED', "
            "'FAILED', 'CANCELLED', 'UNKNOWN_TERMINAL')",
        )
        batch.create_check_constraint(
            "ck_print_jobs_start_progress_range",
            "start_progress IS NULL OR start_progress BETWEEN 0 AND 100",
        )
        batch.create_check_constraint(
            "ck_print_jobs_final_progress_range",
            "final_progress IS NULL OR final_progress BETWEEN 0 AND 100",
        )
        batch.create_check_constraint(
            "ck_print_jobs_start_layer_non_negative",
            "start_layer IS NULL OR start_layer >= 0",
        )
        batch.create_check_constraint(
            "ck_print_jobs_final_layer_non_negative",
            "final_layer IS NULL OR final_layer >= 0",
        )
        batch.create_check_constraint(
            "ck_print_jobs_total_layers_non_negative",
            "total_layers IS NULL OR total_layers >= 0",
        )
        batch.create_check_constraint(
            "ck_print_jobs_duration_non_negative",
            "duration_seconds IS NULL OR duration_seconds >= 0",
        )
        batch.create_check_constraint(
            "ck_print_jobs_remaining_time_non_negative",
            "remaining_time_minutes IS NULL OR remaining_time_minutes >= 0",
        )

    op.create_index("ix_print_jobs_printer_serial", "print_jobs", ["printer_serial"])
    op.create_index("ix_print_jobs_bambu_identity_key", "print_jobs", ["bambu_identity_key"])
    op.create_index(
        "ix_print_jobs_reconciliation_status",
        "print_jobs",
        ["reconciliation_status"],
    )
    op.create_index(
        "uq_print_jobs_one_active_bambu_printer",
        "print_jobs",
        ["printer_serial"],
        unique=True,
        sqlite_where=sa.text(
            "printer_serial IS NOT NULL AND capture_mode IS NOT NULL "
            "AND status IN ('PRINTING', 'PAUSED')"
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    captured_jobs = connection.scalar(
        sa.text("SELECT count(*) FROM print_jobs WHERE capture_mode IS NOT NULL")
    )
    if captured_jobs:
        raise RuntimeError(
            "Cannot downgrade Bambu print history while captured PrintJobs exist; "
            "the downgrade would discard their history."
        )

    op.drop_index("uq_print_jobs_one_active_bambu_printer", table_name="print_jobs")
    op.drop_index("ix_print_jobs_reconciliation_status", table_name="print_jobs")
    op.drop_index("ix_print_jobs_bambu_identity_key", table_name="print_jobs")
    op.drop_index("ix_print_jobs_printer_serial", table_name="print_jobs")

    with op.batch_alter_table("print_jobs") as batch:
        batch.drop_constraint("ck_print_jobs_remaining_time_non_negative", type_="check")
        batch.drop_constraint("ck_print_jobs_duration_non_negative", type_="check")
        batch.drop_constraint("ck_print_jobs_total_layers_non_negative", type_="check")
        batch.drop_constraint("ck_print_jobs_final_layer_non_negative", type_="check")
        batch.drop_constraint("ck_print_jobs_start_layer_non_negative", type_="check")
        batch.drop_constraint("ck_print_jobs_final_progress_range", type_="check")
        batch.drop_constraint("ck_print_jobs_start_progress_range", type_="check")
        batch.drop_constraint("ck_print_jobs_status", type_="check")
        batch.drop_constraint("ck_print_jobs_name_not_blank", type_="check")
        batch.drop_column("ams_snapshot")
        batch.drop_column("reconciliation_status")
        batch.drop_column("capture_mode")
        batch.drop_column("remaining_time_minutes")
        batch.drop_column("duration_seconds")
        batch.drop_column("total_layers")
        batch.drop_column("final_layer")
        batch.drop_column("start_layer")
        batch.drop_column("final_progress")
        batch.drop_column("start_progress")
        batch.drop_column("raw_bambu_state")
        batch.drop_column("last_seen_at")
        batch.drop_column("gcode_file")
        batch.drop_column("profile_id")
        batch.drop_column("project_id")
        batch.drop_column("subtask_id")
        batch.drop_column("task_id")
        batch.drop_column("bambu_identity_key")
        batch.drop_column("printer_serial")
        batch.alter_column("name", existing_type=sa.String(length=200), nullable=False)
        batch.create_check_constraint("ck_print_jobs_name_not_blank", "trim(name) <> ''")
        batch.create_check_constraint(
            "ck_print_jobs_status",
            "status IN ('PLANNED', 'PRINTING', 'SUCCESS', 'FAILED', 'CANCELLED')",
        )
