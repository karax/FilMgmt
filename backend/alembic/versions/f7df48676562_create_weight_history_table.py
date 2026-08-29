"""create weight history table

Revision ID: f7df48676562
Revises: 94794b9aa060
Create Date: 2026-08-29 10:08:55.267505

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f7df48676562"
down_revision: Union[str, Sequence[str], None] = "94794b9aa060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "weight_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("spool_id", sa.Integer(), nullable=False),
        sa.Column(
            "weight_g",
            sa.Numeric(precision=10, scale=3),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "MANUAL",
                "PRINT",
                "SCALE",
                "IMPORT",
                "CORRECTION",
                name="weight_source",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('MANUAL', 'PRINT', 'SCALE', 'IMPORT', 'CORRECTION')",
            name="ck_weight_history_source",
        ),
        sa.CheckConstraint(
            "weight_g >= 0",
            name="ck_weight_history_weight_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["spool_id"],
            ["spools.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "ix_weight_history_spool_id_created_at",
        "weight_history",
        ["spool_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_weight_history_spool_id_created_at",
        table_name="weight_history",
    )
    op.drop_table("weight_history")
