"""create spools table

Revision ID: 94794b9aa060
Revises: 4d6ac1d14d5f
Create Date: 2026-08-29 01:54:58.585463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "94794b9aa060"
down_revision: Union[str, Sequence[str], None] = "4d6ac1d14d5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "spools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("manufacturer_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=True),
        sa.Column("color_name", sa.String(length=100), nullable=False),
        sa.Column("color_hex", sa.String(length=7), nullable=True),
        sa.Column(
            "diameter_mm",
            sa.Numeric(precision=4, scale=2),
            server_default="1.75",
            nullable=False,
        ),
        sa.Column(
            "initial_filament_weight_g",
            sa.Numeric(precision=10, scale=3),
            nullable=False,
        ),
        sa.Column(
            "current_filament_weight_g",
            sa.Numeric(precision=10, scale=3),
            nullable=False,
        ),
        sa.Column(
            "empty_spool_weight_g",
            sa.Numeric(precision=10, scale=3),
            nullable=True,
        ),
        sa.Column(
            "purchase_price",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="EUR",
            nullable=False,
        ),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nozzle_temp_min", sa.Integer(), nullable=True),
        sa.Column("nozzle_temp_max", sa.Integer(), nullable=True),
        sa.Column("bed_temp_min", sa.Integer(), nullable=True),
        sa.Column("bed_temp_max", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "SEALED",
                "OPEN",
                "IN_USE",
                "LOW",
                "EMPTY",
                "NEEDS_DRYING",
                "ARCHIVED",
                name="spool_status",
                native_enum=False,
                create_constraint=False,
                length=20,
            ),
            server_default="SEALED",
            nullable=False,
        ),
        sa.Column(
            "needs_drying",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_dried_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "bed_temp_max IS NULL OR bed_temp_max BETWEEN 0 AND 500",
            name="ck_spools_bed_temp_max_range",
        ),
        sa.CheckConstraint(
            "bed_temp_min IS NULL OR bed_temp_max IS NULL "
            "OR bed_temp_min <= bed_temp_max",
            name="ck_spools_bed_temp_order",
        ),
        sa.CheckConstraint(
            "bed_temp_min IS NULL OR bed_temp_min BETWEEN 0 AND 500",
            name="ck_spools_bed_temp_min_range",
        ),
        sa.CheckConstraint(
            "current_filament_weight_g <= initial_filament_weight_g",
            name="ck_spools_current_weight_not_above_initial",
        ),
        sa.CheckConstraint(
            "current_filament_weight_g >= 0",
            name="ck_spools_current_weight_non_negative",
        ),
        sa.CheckConstraint(
            "diameter_mm >= 0.5 AND diameter_mm <= 5",
            name="ck_spools_diameter_range",
        ),
        sa.CheckConstraint(
            "empty_spool_weight_g IS NULL OR empty_spool_weight_g >= 0",
            name="ck_spools_empty_weight_non_negative",
        ),
        sa.CheckConstraint(
            "initial_filament_weight_g > 0",
            name="ck_spools_initial_weight_positive",
        ),
        sa.CheckConstraint(
            "nozzle_temp_max IS NULL OR nozzle_temp_max BETWEEN 0 AND 500",
            name="ck_spools_nozzle_temp_max_range",
        ),
        sa.CheckConstraint(
            "nozzle_temp_min IS NULL OR nozzle_temp_max IS NULL "
            "OR nozzle_temp_min <= nozzle_temp_max",
            name="ck_spools_nozzle_temp_order",
        ),
        sa.CheckConstraint(
            "nozzle_temp_min IS NULL OR nozzle_temp_min BETWEEN 0 AND 500",
            name="ck_spools_nozzle_temp_min_range",
        ),
        sa.CheckConstraint(
            "purchase_price IS NULL OR purchase_price >= 0",
            name="ck_spools_purchase_price_non_negative",
        ),
        sa.CheckConstraint(
            "status IN ('SEALED', 'OPEN', 'IN_USE', 'LOW', 'EMPTY', "
            "'NEEDS_DRYING', 'ARCHIVED')",
            name="ck_spools_status",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["manufacturer_id"],
            ["manufacturers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["materials.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_spools_code"),
        sqlite_autoincrement=True,
    )
    op.create_index(op.f("ix_spools_code"), "spools", ["code"], unique=False)
    op.create_index(
        op.f("ix_spools_location_id"),
        "spools",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_spools_manufacturer_id"),
        "spools",
        ["manufacturer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_spools_material_id"),
        "spools",
        ["material_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_spools_status"),
        "spools",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_spools_status"), table_name="spools")
    op.drop_index(op.f("ix_spools_material_id"), table_name="spools")
    op.drop_index(op.f("ix_spools_manufacturer_id"), table_name="spools")
    op.drop_index(op.f("ix_spools_location_id"), table_name="spools")
    op.drop_index(op.f("ix_spools_code"), table_name="spools")
    op.drop_table("spools")
