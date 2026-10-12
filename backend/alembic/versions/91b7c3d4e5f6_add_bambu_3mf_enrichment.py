"""add Bambu FTPS 3MF enrichment metadata

Revision ID: 91b7c3d4e5f6
Revises: 6c4f2a9d8e10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "91b7c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "6c4f2a9d8e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("print_jobs") as batch:
        batch.add_column(sa.Column("enrichment_status", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("enrichment_attempts", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("last_enrichment_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("enrichment_error_code", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("metadata_source", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("source_file_name", sa.Text(), nullable=True))
        batch.add_column(sa.Column("source_file_match", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("source_file_modified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("metadata_parser_version", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("thumbnail_file_name", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("selected_plate_index", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("selected_plate_name", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("plate_selection_confidence", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("slicer_estimated_duration_seconds", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "ck_print_jobs_enrichment_attempts_non_negative",
            "enrichment_attempts >= 0",
        )
        batch.create_check_constraint(
            "ck_print_jobs_enrichment_status",
            "enrichment_status IS NULL OR enrichment_status IN ('PENDING', 'IN_PROGRESS', "
            "'ENRICHED', 'FILE_NOT_FOUND', 'AMBIGUOUS', 'RETRYABLE', 'FAILED')",
        )
        batch.create_check_constraint(
            "ck_print_jobs_slicer_duration_non_negative",
            "slicer_estimated_duration_seconds IS NULL OR slicer_estimated_duration_seconds >= 0",
        )

    op.create_index("ix_print_jobs_enrichment_status", "print_jobs", ["enrichment_status"])
    op.execute(
        "UPDATE print_jobs SET enrichment_status = 'PENDING' "
        "WHERE capture_mode IS NOT NULL AND enrichment_status IS NULL"
    )

    op.create_table(
        "print_job_filament_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("print_job_id", sa.Integer(), sa.ForeignKey("print_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("plate_index", sa.Integer(), nullable=True),
        sa.Column("source_filament_id", sa.String(length=100), nullable=True),
        sa.Column("material_type", sa.String(length=100), nullable=True),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("used_g", sa.Numeric(12, 3), nullable=True),
        sa.Column("used_m", sa.Numeric(12, 3), nullable=True),
        sa.Column("tray_info_idx", sa.String(length=100), nullable=True),
        sa.Column("used_for_object", sa.Boolean(), nullable=True),
        sa.Column("used_for_support", sa.Boolean(), nullable=True),
        sa.Column("nozzle_diameter", sa.Numeric(5, 2), nullable=True),
        sa.Column("group_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_print_job_filament_usages_position_non_negative"),
        sa.CheckConstraint("used_g IS NULL OR used_g >= 0", name="ck_print_job_filament_usages_used_g_non_negative"),
        sa.CheckConstraint("used_m IS NULL OR used_m >= 0", name="ck_print_job_filament_usages_used_m_non_negative"),
        sa.CheckConstraint("nozzle_diameter IS NULL OR nozzle_diameter > 0", name="ck_print_job_filament_usages_nozzle_positive"),
        sa.UniqueConstraint("print_job_id", "position", name="uq_print_job_filament_usages_job_position"),
    )
    op.create_index(
        "ix_print_job_filament_usages_print_job_id",
        "print_job_filament_usages",
        ["print_job_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    enriched_rows = connection.scalar(
        sa.text(
            "SELECT count(*) FROM print_jobs WHERE enriched_at IS NOT NULL "
            "OR metadata_source IS NOT NULL OR thumbnail_file_name IS NOT NULL"
        )
    )
    usage_rows = connection.scalar(sa.text("SELECT count(*) FROM print_job_filament_usages"))
    if enriched_rows or usage_rows:
        raise RuntimeError(
            "Cannot downgrade Bambu 3MF enrichment while enriched metadata exists; "
            "the downgrade would discard it."
        )

    op.drop_index("ix_print_job_filament_usages_print_job_id", table_name="print_job_filament_usages")
    op.drop_table("print_job_filament_usages")
    op.drop_index("ix_print_jobs_enrichment_status", table_name="print_jobs")

    with op.batch_alter_table("print_jobs") as batch:
        batch.drop_constraint("ck_print_jobs_slicer_duration_non_negative", type_="check")
        batch.drop_constraint("ck_print_jobs_enrichment_status", type_="check")
        batch.drop_constraint("ck_print_jobs_enrichment_attempts_non_negative", type_="check")
        batch.drop_column("slicer_estimated_duration_seconds")
        batch.drop_column("plate_selection_confidence")
        batch.drop_column("selected_plate_name")
        batch.drop_column("selected_plate_index")
        batch.drop_column("thumbnail_file_name")
        batch.drop_column("enriched_at")
        batch.drop_column("metadata_parser_version")
        batch.drop_column("source_file_modified_at")
        batch.drop_column("source_file_match")
        batch.drop_column("source_file_name")
        batch.drop_column("metadata_source")
        batch.drop_column("enrichment_error_code")
        batch.drop_column("last_enrichment_attempt_at")
        batch.drop_column("enrichment_attempts")
        batch.drop_column("enrichment_status")
