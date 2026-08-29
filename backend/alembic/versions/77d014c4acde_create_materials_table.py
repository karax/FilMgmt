"""create materials table

Revision ID: 77d014c4acde
Revises: b90dd9c87e97
Create Date: 2026-08-29 01:25:00.505136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "77d014c4acde"
down_revision: Union[str, Sequence[str], None] = "b90dd9c87e97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("default_nozzle_temp_min", sa.Integer(), nullable=True),
        sa.Column("default_nozzle_temp_max", sa.Integer(), nullable=True),
        sa.Column("default_bed_temp_min", sa.Integer(), nullable=True),
        sa.Column("default_bed_temp_max", sa.Integer(), nullable=True),
        sa.Column(
            "density_g_cm3",
            sa.Numeric(precision=5, scale=3),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_materials_name"),
    )
    op.create_index(
        op.f("ix_materials_name"),
        "materials",
        ["name"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_materials_name"), table_name="materials")
    op.drop_table("materials")
