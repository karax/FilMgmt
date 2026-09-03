"""remove spool storage and add purchase store name

Revision ID: f2a8c7d190b4
Revises: b33a1c9d2e71
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a8c7d190b4"
down_revision: Union[str, Sequence[str], None] = "b33a1c9d2e71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove location storage data and add an optional purchase store."""
    with op.batch_alter_table("spools") as batch_op:
        batch_op.drop_index(op.f("ix_spools_location_id"))
        batch_op.drop_column("location_id")
        batch_op.add_column(sa.Column("store_name", sa.String(200), nullable=True))

    op.drop_index(op.f("ix_locations_name"), table_name="locations")
    op.drop_table("locations")


def downgrade() -> None:
    """Restore the retired location catalog without its deleted data."""
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("name", name="uq_locations_name"),
    )
    op.create_index(op.f("ix_locations_name"), "locations", ["name"])

    with op.batch_alter_table("spools") as batch_op:
        batch_op.drop_column("store_name")
        batch_op.add_column(sa.Column("location_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_spools_location_id_locations",
            "locations",
            ["location_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_spools_location_id"),
            ["location_id"],
        )
