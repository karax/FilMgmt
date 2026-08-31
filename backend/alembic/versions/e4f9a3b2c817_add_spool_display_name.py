"""add spool display name

Revision ID: e4f9a3b2c817
Revises: d3e8b9f67124
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4f9a3b2c817"
down_revision: Union[str, Sequence[str], None] = "d3e8b9f67124"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("spools") as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(150), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("spools") as batch_op:
        batch_op.drop_column("display_name")
