"""add analytics query indexes

Revision ID: d7a1e6b4c902
Revises: c5f9d2a7e641
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d7a1e6b4c902"
down_revision: Union[str, Sequence[str], None] = "c5f9d2a7e641"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_print_jobs_started_at", "print_jobs", ["started_at"])
    op.create_index("ix_spools_purchase_date", "spools", ["purchase_date"])
    op.create_index(
        "ix_reconciliation_active_consumption_job_spool",
        "print_job_filament_reconciliations",
        ["print_job_id", "spool_id"],
        sqlite_where=sa.text("event_type = 'CONSUMPTION' AND reversed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reconciliation_active_consumption_job_spool",
        table_name="print_job_filament_reconciliations",
    )
    op.drop_index("ix_spools_purchase_date", table_name="spools")
    op.drop_index("ix_print_jobs_started_at", table_name="print_jobs")

