"""add unique index for active print spool

Revision ID: c2d7a5f48b91
Revises: a18f4c9d0e62
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d7a5f48b91"
down_revision: Union[str, Sequence[str], None] = "a18f4c9d0e62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_print_jobs_one_printing_per_spool",
        "print_jobs",
        ["spool_id"],
        unique=True,
        sqlite_where=sa.text("status = 'PRINTING'"),
    )


def downgrade() -> None:
    op.drop_index("uq_print_jobs_one_printing_per_spool", table_name="print_jobs")
