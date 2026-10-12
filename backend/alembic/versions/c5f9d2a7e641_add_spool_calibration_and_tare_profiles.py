"""add spool calibration and tare profiles

Revision ID: c5f9d2a7e641
Revises: a4e8c1f2b7d9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c5f9d2a7e641"
down_revision: Union[str, Sequence[str], None] = "a4e8c1f2b7d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tare_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("manufacturer", sa.String(length=150), nullable=True),
        sa.Column("spool_type", sa.String(length=150), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tare_g", sa.Numeric(10, 3), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.String(length=10), nullable=False),
        sa.Column("measured_sample_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("measured_min_g", sa.Numeric(10, 3), nullable=True),
        sa.Column("measured_max_g", sa.Numeric(10, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("trim(name) <> ''", name="ck_tare_profiles_name_not_blank"),
        sa.CheckConstraint("tare_g >= 0", name="ck_tare_profiles_tare_non_negative"),
        sa.CheckConstraint("source IN ('MEASURED', 'KNOWN', 'ESTIMATED', 'MANUAL')", name="ck_tare_profiles_source"),
        sa.CheckConstraint("confidence IN ('HIGH', 'MEDIUM', 'LOW')", name="ck_tare_profiles_confidence"),
        sa.CheckConstraint("measured_sample_count >= 0", name="ck_tare_profiles_sample_count_non_negative"),
        sa.CheckConstraint("measured_min_g IS NULL OR measured_min_g >= 0", name="ck_tare_profiles_min_non_negative"),
        sa.CheckConstraint("measured_max_g IS NULL OR measured_max_g >= 0", name="ck_tare_profiles_max_non_negative"),
        sa.UniqueConstraint("name", name="uq_tare_profiles_name"),
        sqlite_autoincrement=True,
    )

    op.create_table(
        "spool_calibrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spool_id", sa.Integer(), sa.ForeignKey("spools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("measured_total_g", sa.Numeric(10, 3), nullable=True),
        sa.Column("tare_g_used", sa.Numeric(10, 3), nullable=True),
        sa.Column("calculated_filament_g", sa.Numeric(10, 3), nullable=True),
        sa.Column("previous_remaining_g", sa.Numeric(10, 3), nullable=False),
        sa.Column("adjustment_g", sa.Numeric(12, 3), nullable=False),
        sa.Column("new_remaining_g", sa.Numeric(10, 3), nullable=False),
        sa.Column("tare_source_used", sa.String(length=20), nullable=True),
        sa.Column("tare_confidence_used", sa.String(length=10), nullable=True),
        sa.Column("tare_profile_id", sa.Integer(), sa.ForeignKey("tare_profiles.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("reversed_calibration_id", sa.Integer(), sa.ForeignKey("spool_calibrations.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("event_type IN ('PHYSICAL_CALIBRATION', 'REVERSAL')", name="ck_spool_calibrations_event_type"),
        sa.CheckConstraint("measured_total_g IS NULL OR measured_total_g >= 0", name="ck_spool_calibrations_total_non_negative"),
        sa.CheckConstraint("tare_g_used IS NULL OR tare_g_used >= 0", name="ck_spool_calibrations_tare_non_negative"),
        sa.CheckConstraint("calculated_filament_g IS NULL OR calculated_filament_g >= 0", name="ck_spool_calibrations_filament_non_negative"),
        sa.CheckConstraint("previous_remaining_g >= 0", name="ck_spool_calibrations_before_non_negative"),
        sa.CheckConstraint("new_remaining_g >= 0", name="ck_spool_calibrations_after_non_negative"),
        sa.CheckConstraint("tare_source_used IS NULL OR tare_source_used IN ('MEASURED', 'KNOWN', 'ESTIMATED', 'MANUAL')", name="ck_spool_calibrations_tare_source"),
        sa.CheckConstraint("tare_confidence_used IS NULL OR tare_confidence_used IN ('HIGH', 'MEDIUM', 'LOW')", name="ck_spool_calibrations_tare_confidence"),
        sa.CheckConstraint(
            "(event_type = 'PHYSICAL_CALIBRATION' AND measured_total_g IS NOT NULL "
            "AND tare_g_used IS NOT NULL AND calculated_filament_g IS NOT NULL "
            "AND tare_source_used IS NOT NULL AND tare_confidence_used IS NOT NULL "
            "AND idempotency_key IS NOT NULL AND reversed_calibration_id IS NULL) "
            "OR (event_type = 'REVERSAL' AND reversed_calibration_id IS NOT NULL)",
            name="ck_spool_calibrations_event_shape",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_spool_calibrations_idempotency"),
        sa.UniqueConstraint("reversed_calibration_id", name="uq_spool_calibrations_reversed"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_spool_calibrations_spool_id", "spool_calibrations", ["spool_id"])
    op.create_index("ix_spool_calibrations_tare_profile_id", "spool_calibrations", ["tare_profile_id"])
    op.create_index("ix_spool_calibrations_spool_effective", "spool_calibrations", ["spool_id", "effective_at"])

    op.create_table(
        "tare_measurements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spool_id", sa.Integer(), sa.ForeignKey("spools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tare_profile_id", sa.Integer(), sa.ForeignKey("tare_profiles.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("measured_tare_g", sa.Numeric(10, 3), nullable=False),
        sa.Column("contributes_to_profile", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("measured_tare_g >= 0", name="ck_tare_measurements_non_negative"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_tare_measurements_spool_id", "tare_measurements", ["spool_id"])
    op.create_index("ix_tare_measurements_tare_profile_id", "tare_measurements", ["tare_profile_id"])
    op.create_index("ix_tare_measurements_profile_created", "tare_measurements", ["tare_profile_id", "created_at"])


def downgrade() -> None:
    connection = op.get_bind()
    if any(
        connection.scalar(sa.text(f"SELECT count(*) FROM {table}"))
        for table in ("spool_calibrations", "tare_measurements", "tare_profiles")
    ):
        raise RuntimeError(
            "Cannot downgrade spool calibration while calibration or tare history exists; "
            "the downgrade would discard its audit trail."
        )
    op.drop_index("ix_tare_measurements_profile_created", table_name="tare_measurements")
    op.drop_index("ix_tare_measurements_tare_profile_id", table_name="tare_measurements")
    op.drop_index("ix_tare_measurements_spool_id", table_name="tare_measurements")
    op.drop_table("tare_measurements")
    op.drop_index("ix_spool_calibrations_spool_effective", table_name="spool_calibrations")
    op.drop_index("ix_spool_calibrations_tare_profile_id", table_name="spool_calibrations")
    op.drop_index("ix_spool_calibrations_spool_id", table_name="spool_calibrations")
    op.drop_table("spool_calibrations")
    op.drop_table("tare_profiles")
