"""add print job material cost snapshot

Revision ID: d3e8b9f67124
Revises: c2d7a5f48b91
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e8b9f67124"
down_revision: Union[str, Sequence[str], None] = "c2d7a5f48b91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("print_jobs") as batch_op:
        batch_op.add_column(sa.Column("filament_cost_per_g", sa.Numeric(12, 6), nullable=True))
        batch_op.add_column(sa.Column("material_cost", sa.Numeric(12, 4), nullable=True))
        batch_op.add_column(sa.Column("material_cost_currency", sa.String(3), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("print_jobs") as batch_op:
        batch_op.drop_column("material_cost_currency")
        batch_op.drop_column("material_cost")
        batch_op.drop_column("filament_cost_per_g")
