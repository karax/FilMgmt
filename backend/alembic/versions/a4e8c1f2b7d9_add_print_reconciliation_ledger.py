"""add print reconciliation ledger

Revision ID: a4e8c1f2b7d9
Revises: 91b7c3d4e5f6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a4e8c1f2b7d9"
down_revision: Union[str, Sequence[str], None] = "91b7c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("print_jobs") as batch:
        batch.create_check_constraint(
            "ck_print_jobs_reconciliation_status",
            "reconciliation_status IS NULL OR reconciliation_status IN "
            "('PENDING', 'PARTIALLY_RECONCILED', 'RECONCILED', "
            "'NEEDS_REVIEW', 'NOT_APPLICABLE')",
        )

    op.create_table(
        "print_job_filament_reconciliations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "print_job_id",
            sa.Integer(),
            sa.ForeignKey("print_jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "filament_usage_id",
            sa.Integer(),
            sa.ForeignKey("print_job_filament_usages.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "spool_id",
            sa.Integer(),
            sa.ForeignKey("spools.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("amount_g", sa.Numeric(12, 3), nullable=False),
        sa.Column("sliced_estimated_g", sa.Numeric(12, 3), nullable=True),
        sa.Column("remaining_before_g", sa.Numeric(10, 3), nullable=True),
        sa.Column("remaining_after_g", sa.Numeric(10, 3), nullable=True),
        sa.Column("manual_override", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "reversed_event_id",
            sa.Integer(),
            sa.ForeignKey("print_job_filament_reconciliations.id", ondelete="RESTRICT"),
            nullable=True,
            unique=True,
        ),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_g >= 0", name="ck_filament_reconciliation_amount_non_negative"
        ),
        sa.CheckConstraint(
            "event_type IN ('CONSUMPTION', 'SKIP', 'REVERSAL')",
            name="ck_filament_reconciliation_event_type",
        ),
        sa.CheckConstraint(
            "(event_type = 'CONSUMPTION' AND spool_id IS NOT NULL AND amount_g > 0 "
            "AND remaining_before_g IS NOT NULL AND remaining_after_g IS NOT NULL) "
            "OR (event_type = 'SKIP' AND spool_id IS NULL AND amount_g = 0 "
            "AND remaining_before_g IS NULL AND remaining_after_g IS NULL) "
            "OR (event_type = 'REVERSAL' AND reversed_event_id IS NOT NULL)",
            name="ck_filament_reconciliation_event_shape",
        ),
    )
    op.create_index(
        "ix_print_job_filament_reconciliations_print_job_id",
        "print_job_filament_reconciliations",
        ["print_job_id"],
    )
    op.create_index(
        "ix_print_job_filament_reconciliations_filament_usage_id",
        "print_job_filament_reconciliations",
        ["filament_usage_id"],
    )
    op.create_index(
        "ix_print_job_filament_reconciliations_spool_id",
        "print_job_filament_reconciliations",
        ["spool_id"],
    )
    op.create_index(
        "uq_active_filament_reconciliation",
        "print_job_filament_reconciliations",
        ["filament_usage_id"],
        unique=True,
        sqlite_where=sa.text(
            "event_type IN ('CONSUMPTION', 'SKIP') AND reversed_at IS NULL"
        ),
    )

    # Existing enriched terminal jobs become eligible without touching stock.
    op.execute(
        "UPDATE print_jobs SET reconciliation_status = "
        "CASE WHEN status IN ('FAILED', 'CANCELLED', 'UNKNOWN_TERMINAL') "
        "THEN 'NEEDS_REVIEW' ELSE 'PENDING' END "
        "WHERE enrichment_status = 'ENRICHED' "
        "AND status IN ('COMPLETED', 'SUCCESS', 'FAILED', 'CANCELLED', 'UNKNOWN_TERMINAL') "
        "AND EXISTS (SELECT 1 FROM print_job_filament_usages usage "
        "WHERE usage.print_job_id = print_jobs.id)"
    )


def downgrade() -> None:
    connection = op.get_bind()
    event_count = connection.scalar(
        sa.text("SELECT count(*) FROM print_job_filament_reconciliations")
    )
    new_status_count = connection.scalar(
        sa.text(
            "SELECT count(*) FROM print_jobs WHERE reconciliation_status "
            "IN ('PARTIALLY_RECONCILED', 'RECONCILED', 'NOT_APPLICABLE')"
        )
    )
    if event_count or new_status_count:
        raise RuntimeError(
            "Cannot downgrade print reconciliation while reconciliation history exists; "
            "the downgrade would discard its audit trail."
        )

    op.drop_index(
        "uq_active_filament_reconciliation",
        table_name="print_job_filament_reconciliations",
    )
    op.drop_index(
        "ix_print_job_filament_reconciliations_spool_id",
        table_name="print_job_filament_reconciliations",
    )
    op.drop_index(
        "ix_print_job_filament_reconciliations_filament_usage_id",
        table_name="print_job_filament_reconciliations",
    )
    op.drop_index(
        "ix_print_job_filament_reconciliations_print_job_id",
        table_name="print_job_filament_reconciliations",
    )
    op.drop_table("print_job_filament_reconciliations")

    with op.batch_alter_table("print_jobs") as batch:
        batch.drop_constraint("ck_print_jobs_reconciliation_status", type_="check")
