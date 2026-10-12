from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from io import StringIO
from typing import Any

from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.orm import Session, aliased

from app.models import (
    CalibrationEventType,
    FilamentReconciliationEventType,
    Manufacturer,
    Material,
    PrintJob,
    PrintJobFilamentReconciliation,
    PrintJobFilamentUsage,
    Spool,
    SpoolCalibration,
    TareProfile,
    WeightHistory,
)
from app.models.timestamps import normalize_utc
from app.schemas.analytics import AnalyticsBucket, AnalyticsRangePreset
from app.services.analytics_service import AnalyticsDateRange, AnalyticsFilters, AnalyticsService


class ExportDataset(StrEnum):
    SPOOLS = "spools"
    PRINTS = "prints"
    FILAMENT_USAGE = "filament_usage"
    CONFIRMED_CONSUMPTION = "confirmed_consumption"
    PURCHASES = "purchases"
    LEDGER = "ledger"
    CALIBRATIONS = "calibrations"
    CONSUMPTION_OVER_TIME = "consumption_over_time"
    TOP_SPOOLS = "top_spools"
    CONSUMPTION_BY_MATERIAL = "consumption_by_material"
    CONSUMPTION_BY_BRAND = "consumption_by_brand"
    INVENTORY_BY_MATERIAL = "inventory_by_material"
    PURCHASES_BY_STORE = "purchases_by_store"
    PURCHASE_SPEND_OVER_TIME = "purchase_spend_over_time"
    PRINT_OUTCOMES = "print_outcomes"
    PRINT_ACTIVITY = "print_activity"
    LARGEST_CONSUMING_PRINTS = "largest_consuming_prints"


class ExportScope(StrEnum):
    CURRENT = "current"
    ALL = "all"


class ExportScopeError(ValueError):
    pass


@dataclass(frozen=True)
class ExportColumn:
    name: str
    text: bool = False


@dataclass(frozen=True)
class DatasetDefinition:
    filename_slug: str
    analytics: bool
    columns: tuple[ExportColumn, ...]


def _columns(*names: str, text: tuple[str, ...] = ()) -> tuple[ExportColumn, ...]:
    return tuple(ExportColumn(name, name in text) for name in names)


DATASET_DEFINITIONS: dict[ExportDataset, DatasetDefinition] = {
    ExportDataset.SPOOLS: DatasetDefinition(
        "spool-inventory",
        False,
        _columns(
            "spool_id", "code", "display_name", "product_name", "brand", "material",
            "color_name", "color_hex", "status", "diameter_mm", "nominal_weight_g",
            "remaining_weight_g", "empty_spool_weight_g", "purchase_price",
            "purchase_currency", "purchase_store", "purchase_date", "opened_at",
            "last_used_at", "needs_drying", "notes", "created_at", "updated_at",
            "archived_at", "last_calibration_at", "last_calibration_tare_g",
            "last_calibration_tare_source", "last_calibration_tare_profile",
            text=("code", "display_name", "product_name", "brand", "material", "color_name", "color_hex", "status", "purchase_currency", "purchase_store", "notes", "last_calibration_tare_source", "last_calibration_tare_profile"),
        ),
    ),
    ExportDataset.PRINTS: DatasetDefinition(
        "print-history",
        False,
        _columns(
            "print_job_id", "printer_serial", "printer_name", "name", "gcode_file",
            "plate_index", "plate_name", "started_at", "finished_at", "status",
            "actual_duration_seconds", "final_progress", "final_layer", "total_layers",
            "estimated_filament_g", "estimated_filament_m",
            "slicer_estimated_duration_seconds", "reconciliation_status", "capture_mode",
            "notes", "created_at", "updated_at",
            text=("printer_serial", "printer_name", "name", "gcode_file", "plate_name", "status", "reconciliation_status", "capture_mode", "notes"),
        ),
    ),
    ExportDataset.FILAMENT_USAGE: DatasetDefinition(
        "print-filament-usage",
        False,
        _columns(
            "print_job_id", "filament_usage_id", "print_name", "print_started_at",
            "position", "plate_index", "source_filament_id", "sliced_material",
            "sliced_color", "estimated_used_g", "estimated_used_m", "tray_info_idx",
            "used_for_object", "used_for_support", "nozzle_diameter", "group_id",
            "confirmed_spool_id", "confirmed_spool_code", "confirmed_spool_brand",
            "confirmed_spool_material", "confirmed_spool_color",
            "confirmed_consumption_g", "reconciliation_status", "reconciliation_date",
            text=("print_name", "source_filament_id", "sliced_material", "sliced_color", "tray_info_idx", "group_id", "confirmed_spool_code", "confirmed_spool_brand", "confirmed_spool_material", "confirmed_spool_color", "reconciliation_status"),
        ),
    ),
    ExportDataset.CONFIRMED_CONSUMPTION: DatasetDefinition(
        "confirmed-consumption",
        False,
        _columns(
            "effective_print_date", "print_job_id", "print_name", "filament_usage_id",
            "spool_id", "spool_code", "spool_name", "brand", "material", "color",
            "confirmed_consumption_g", "estimated_sliced_g", "purchase_unit_cost_per_g",
            "estimated_material_cost", "currency", "reconciliation_date",
            text=("print_name", "spool_code", "spool_name", "brand", "material", "color", "currency"),
        ),
    ),
    ExportDataset.PURCHASES: DatasetDefinition(
        "purchases",
        False,
        _columns(
            "spool_id", "spool_code", "purchase_date", "store", "brand", "material",
            "color", "nominal_weight_g", "price", "currency", "cost_per_g",
            "cost_per_kg",
            text=("spool_code", "store", "brand", "material", "color", "currency"),
        ),
    ),
    ExportDataset.LEDGER: DatasetDefinition(
        "inventory-ledger",
        False,
        _columns(
            "event_domain", "event_id", "spool_id", "spool_code", "event_type",
            "effective_at", "created_at", "amount_g", "balance_before_g",
            "balance_after_g", "print_job_id", "filament_usage_id",
            "reversal_of_event_id", "reason", "note",
            text=("event_domain", "spool_code", "event_type", "reason", "note"),
        ),
    ),
    ExportDataset.CALIBRATIONS: DatasetDefinition(
        "physical-calibrations",
        False,
        _columns(
            "calibration_id", "spool_id", "spool_code", "event_type", "calibrated_at",
            "measured_total_g", "tare_g", "physical_filament_g", "expected_before_g",
            "adjustment_g", "balance_after_g", "tare_source", "tare_confidence",
            "tare_profile_id", "tare_profile", "note", "reversal_of_calibration_id",
            "reversed_at", "created_at",
            text=("spool_code", "event_type", "tare_source", "tare_confidence", "tare_profile", "note"),
        ),
    ),
    ExportDataset.CONSUMPTION_OVER_TIME: DatasetDefinition("confirmed-consumption-over-time", True, _columns("period", "consumption_g", text=("period",))),
    ExportDataset.TOP_SPOOLS: DatasetDefinition("top-spools", True, _columns("rank", "spool_id", "code", "display_name", "brand", "material", "color", "consumption_g", "print_count", text=("code", "display_name", "brand", "material", "color"))),
    ExportDataset.CONSUMPTION_BY_MATERIAL: DatasetDefinition("consumption-by-material", True, _columns("rank", "material", "consumption_g", "print_count", text=("material",))),
    ExportDataset.CONSUMPTION_BY_BRAND: DatasetDefinition("consumption-by-brand", True, _columns("rank", "brand", "consumption_g", "print_count", text=("brand",))),
    ExportDataset.INVENTORY_BY_MATERIAL: DatasetDefinition("inventory-by-material", True, _columns("rank", "material", "remaining_g", "spool_count", text=("material",))),
    ExportDataset.PURCHASES_BY_STORE: DatasetDefinition("purchases-by-store", True, _columns("ranking_type", "rank", "store", "currency", "amount", "priced_spool_count", "spool_count", text=("ranking_type", "store", "currency"))),
    ExportDataset.PURCHASE_SPEND_OVER_TIME: DatasetDefinition("purchase-spend-over-time", True, _columns("period", "currency", "amount", text=("period", "currency"))),
    ExportDataset.PRINT_OUTCOMES: DatasetDefinition("print-outcomes", True, _columns("outcome", "count", "success_rate_percentage", text=("outcome",))),
    ExportDataset.PRINT_ACTIVITY: DatasetDefinition("printer-activity", True, _columns("period", "printing_seconds", "completed_print_count", text=("period",))),
    ExportDataset.LARGEST_CONSUMING_PRINTS: DatasetDefinition("largest-consuming-prints", True, _columns("rank", "print_job_id", "name", "started_at", "consumption_g", text=("name",))),
}


@dataclass(frozen=True)
class CsvExport:
    filename: str
    columns: tuple[ExportColumn, ...]
    rows: Iterable[Mapping[str, Any]]

    def stream(self) -> Iterator[bytes]:
        buffer = StringIO(newline="")
        writer = csv.writer(buffer, dialect="excel", lineterminator="\r\n")
        yield b"\xef\xbb\xbf"
        writer.writerow([column.name for column in self.columns])
        yield _drain(buffer)
        for row in self.rows:
            writer.writerow([
                _csv_value(row.get(column.name), text=column.text)
                for column in self.columns
            ])
            yield _drain(buffer)


class CsvExportService:
    """Stream allowlisted CSV datasets from canonical read-only queries."""

    def __init__(
        self,
        db: Session,
        analytics: AnalyticsService,
        dataset: ExportDataset,
        scope: ExportScope,
        bucket: AnalyticsBucket,
    ) -> None:
        definition = DATASET_DEFINITIONS[dataset]
        if definition.analytics and scope is ExportScope.ALL:
            raise ExportScopeError("Analytics exports always use the current Analytics filters.")
        self.db = db
        self.dataset = dataset
        self.scope = scope
        self.bucket = bucket
        self.analytics = analytics if scope is ExportScope.CURRENT else AnalyticsService(
            db,
            AnalyticsDateRange.resolve(
                AnalyticsRangePreset.ALL_TIME,
                None,
                None,
                analytics.date_range.timezone.key,
            ),
            AnalyticsFilters(),
        )

    def build(self) -> CsvExport:
        definition = DATASET_DEFINITIONS[self.dataset]
        suffix = (
            self.analytics.date_range.preset.value.replace("_", "-")
            if self.scope is ExportScope.CURRENT
            else "all-data"
        )
        today = datetime.now(self.analytics.date_range.timezone).date().isoformat()
        filename = f"{definition.filename_slug}-{suffix}-{today}.csv"
        rows = getattr(self, f"_rows_{self.dataset.value}")()
        return CsvExport(filename, definition.columns, rows)

    def _stream(self, statement) -> Iterator[Mapping[str, Any]]:
        result = self.db.execute(statement.execution_options(yield_per=500))
        try:
            yield from result.mappings()
        finally:
            result.close()

    def _rows_spools(self) -> Iterator[Mapping[str, Any]]:
        latest = (
            select(SpoolCalibration)
            .where(
                SpoolCalibration.spool_id == Spool.id,
                SpoolCalibration.event_type == CalibrationEventType.PHYSICAL_CALIBRATION,
                SpoolCalibration.reversed_at.is_(None),
            )
            .order_by(SpoolCalibration.effective_at.desc(), SpoolCalibration.id.desc())
            .limit(1)
            .correlate(Spool)
        )
        statement = self.analytics.spool_select(
            Spool.id.label("spool_id"), Spool.code, Spool.display_name, Spool.product_name,
            Manufacturer.name.label("brand"), Material.name.label("material"),
            Spool.color_name, Spool.color_hex, Spool.status, Spool.diameter_mm,
            Spool.initial_filament_weight_g.label("nominal_weight_g"),
            Spool.current_filament_weight_g.label("remaining_weight_g"),
            Spool.empty_spool_weight_g, Spool.purchase_price,
            Spool.currency.label("purchase_currency"), Spool.store_name.label("purchase_store"),
            Spool.purchase_date, Spool.opened_at, Spool.last_used_at, Spool.needs_drying,
            Spool.notes, Spool.created_at, Spool.updated_at, Spool.archived_at,
            latest.with_only_columns(SpoolCalibration.effective_at).scalar_subquery().label("last_calibration_at"),
            latest.with_only_columns(SpoolCalibration.tare_g_used).scalar_subquery().label("last_calibration_tare_g"),
            latest.with_only_columns(SpoolCalibration.tare_source_used).scalar_subquery().label("last_calibration_tare_source"),
            latest.with_only_columns(
                select(TareProfile.name).where(TareProfile.id == SpoolCalibration.tare_profile_id).scalar_subquery()
            ).scalar_subquery().label("last_calibration_tare_profile"),
        ).order_by(Spool.id)
        yield from self._stream(statement)

    def _rows_prints(self) -> Iterator[Mapping[str, Any]]:
        usage_count = select(func.count(PrintJobFilamentUsage.id)).where(PrintJobFilamentUsage.print_job_id == PrintJob.id).correlate(PrintJob).scalar_subquery()
        known_g = select(func.count(PrintJobFilamentUsage.used_g)).where(PrintJobFilamentUsage.print_job_id == PrintJob.id).correlate(PrintJob).scalar_subquery()
        known_m = select(func.count(PrintJobFilamentUsage.used_m)).where(PrintJobFilamentUsage.print_job_id == PrintJob.id).correlate(PrintJob).scalar_subquery()
        sum_g = select(func.sum(PrintJobFilamentUsage.used_g)).where(PrintJobFilamentUsage.print_job_id == PrintJob.id).correlate(PrintJob).scalar_subquery()
        sum_m = select(func.sum(PrintJobFilamentUsage.used_m)).where(PrintJobFilamentUsage.print_job_id == PrintJob.id).correlate(PrintJob).scalar_subquery()
        statement = self.analytics.print_select(
            PrintJob.id.label("print_job_id"), PrintJob.printer_serial, PrintJob.printer_name,
            PrintJob.name, PrintJob.gcode_file, PrintJob.selected_plate_index.label("plate_index"),
            PrintJob.selected_plate_name.label("plate_name"), PrintJob.started_at,
            PrintJob.finished_at, PrintJob.status,
            PrintJob.duration_seconds.label("actual_duration_seconds"), PrintJob.final_progress,
            PrintJob.final_layer, PrintJob.total_layers,
            case((and_(usage_count > 0, usage_count == known_g), sum_g), else_=None).label("estimated_filament_g"),
            case((and_(usage_count > 0, usage_count == known_m), sum_m), else_=None).label("estimated_filament_m"),
            PrintJob.slicer_estimated_duration_seconds, PrintJob.reconciliation_status,
            PrintJob.capture_mode, PrintJob.notes, PrintJob.created_at, PrintJob.updated_at,
        ).order_by(PrintJob.started_at, PrintJob.id)
        yield from self._stream(statement)

    def _rows_filament_usage(self) -> Iterator[Mapping[str, Any]]:
        event = aliased(PrintJobFilamentReconciliation)
        confirmed_spool = aliased(Spool)
        confirmed_brand = aliased(Manufacturer)
        confirmed_material = aliased(Material)
        status = case(
            (event.event_type == FilamentReconciliationEventType.CONSUMPTION, "CONFIRMED"),
            (event.event_type == FilamentReconciliationEventType.SKIP, "SKIPPED"),
            else_="PENDING",
        ).label("reconciliation_status")
        statement = (
            self.analytics.print_select(
                PrintJob.id.label("print_job_id"), PrintJobFilamentUsage.id.label("filament_usage_id"),
                PrintJob.name.label("print_name"), PrintJob.started_at.label("print_started_at"),
                PrintJobFilamentUsage.position, PrintJobFilamentUsage.plate_index,
                PrintJobFilamentUsage.source_filament_id,
                PrintJobFilamentUsage.material_type.label("sliced_material"),
                PrintJobFilamentUsage.color.label("sliced_color"),
                PrintJobFilamentUsage.used_g.label("estimated_used_g"),
                PrintJobFilamentUsage.used_m.label("estimated_used_m"),
                PrintJobFilamentUsage.tray_info_idx, PrintJobFilamentUsage.used_for_object,
                PrintJobFilamentUsage.used_for_support, PrintJobFilamentUsage.nozzle_diameter,
                PrintJobFilamentUsage.group_id, confirmed_spool.id.label("confirmed_spool_id"),
                confirmed_spool.code.label("confirmed_spool_code"),
                confirmed_brand.name.label("confirmed_spool_brand"),
                confirmed_material.name.label("confirmed_spool_material"),
                confirmed_spool.color_name.label("confirmed_spool_color"),
                event.amount_g.label("confirmed_consumption_g"), status,
                event.created_at.label("reconciliation_date"),
            )
            .join(PrintJobFilamentUsage, PrintJobFilamentUsage.print_job_id == PrintJob.id)
            .outerjoin(event, and_(
                event.filament_usage_id == PrintJobFilamentUsage.id,
                event.event_type.in_((FilamentReconciliationEventType.CONSUMPTION, FilamentReconciliationEventType.SKIP)),
                event.reversed_at.is_(None),
            ))
            .outerjoin(confirmed_spool, confirmed_spool.id == event.spool_id)
            .outerjoin(confirmed_brand, confirmed_brand.id == confirmed_spool.manufacturer_id)
            .outerjoin(confirmed_material, confirmed_material.id == confirmed_spool.material_id)
            .order_by(PrintJob.id, PrintJobFilamentUsage.position)
        )
        for row in self._stream(statement):
            values = dict(row)
            if values["reconciliation_status"] != "CONFIRMED":
                values["confirmed_consumption_g"] = None
            yield values

    def _rows_confirmed_consumption(self) -> Iterator[Mapping[str, Any]]:
        statement = self.analytics.confirmed_consumption_select(
            PrintJob.started_at.label("effective_print_date"), PrintJob.id.label("print_job_id"),
            PrintJob.name.label("print_name"), PrintJobFilamentUsage.id.label("filament_usage_id"),
            Spool.id.label("spool_id"), Spool.code.label("spool_code"),
            func.coalesce(Spool.display_name, Spool.product_name, Spool.code).label("spool_name"),
            Manufacturer.name.label("brand"), Material.name.label("material"),
            Spool.color_name.label("color"),
            PrintJobFilamentReconciliation.amount_g.label("confirmed_consumption_g"),
            PrintJobFilamentReconciliation.sliced_estimated_g.label("estimated_sliced_g"),
            Spool.purchase_price, Spool.initial_filament_weight_g, Spool.currency,
            PrintJobFilamentReconciliation.created_at.label("reconciliation_date"),
        ).order_by(PrintJob.started_at, PrintJobFilamentReconciliation.id)
        for row in self._stream(statement):
            values = dict(row)
            price = values.pop("purchase_price")
            purchased_g = values.pop("initial_filament_weight_g")
            if price is not None and purchased_g is not None and purchased_g > 0:
                unit_cost = Decimal(price) / Decimal(purchased_g)
                values["purchase_unit_cost_per_g"] = unit_cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                values["estimated_material_cost"] = (Decimal(values["confirmed_consumption_g"]) * unit_cost).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            else:
                values["purchase_unit_cost_per_g"] = None
                values["estimated_material_cost"] = None
            yield values

    def _rows_purchases(self) -> Iterator[Mapping[str, Any]]:
        statement = self.analytics.purchase_select(
            Spool.id.label("spool_id"), Spool.code.label("spool_code"), Spool.purchase_date,
            Spool.store_name.label("store"), Manufacturer.name.label("brand"),
            Material.name.label("material"), Spool.color_name.label("color"),
            Spool.initial_filament_weight_g.label("nominal_weight_g"),
            Spool.purchase_price.label("price"), Spool.currency,
        ).order_by(Spool.purchase_date, Spool.id)
        for row in self._stream(statement):
            values = dict(row)
            price = values["price"]
            weight = values["nominal_weight_g"]
            if price is not None and weight is not None and weight > 0:
                per_g = Decimal(price) / Decimal(weight)
                values["cost_per_g"] = per_g.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                values["cost_per_kg"] = (per_g * Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                values["cost_per_g"] = None
                values["cost_per_kg"] = None
            yield values

    def _rows_ledger(self) -> Iterator[Mapping[str, Any]]:
        reconciliation = aliased(PrintJobFilamentReconciliation)
        recon_statement = (
            select(
                literal("reconciliation").label("event_domain"), reconciliation.id.label("event_id"),
                reconciliation.spool_id, Spool.code.label("spool_code"),
                reconciliation.event_type, reconciliation.created_at.label("effective_at"),
                reconciliation.created_at, reconciliation.amount_g, reconciliation.remaining_before_g.label("balance_before_g"),
                reconciliation.remaining_after_g.label("balance_after_g"), reconciliation.print_job_id,
                reconciliation.filament_usage_id, reconciliation.reversed_event_id.label("reversal_of_event_id"),
                reconciliation.reason, literal(None).label("note"),
            )
            .select_from(reconciliation)
            .outerjoin(Spool, Spool.id == reconciliation.spool_id)
            .outerjoin(Material, Material.id == Spool.material_id)
            .outerjoin(Manufacturer, Manufacturer.id == Spool.manufacturer_id)
            .where(*self.analytics.date_conditions(reconciliation.created_at), *self.analytics.spool_conditions())
            .order_by(reconciliation.id)
        )
        for row in self._stream(recon_statement):
            values = dict(row)
            amount = Decimal(values["amount_g"] or 0)
            if values["event_type"] is FilamentReconciliationEventType.CONSUMPTION:
                values["event_type"] = "PRINT_CONSUMPTION"
                values["amount_g"] = -amount
            elif values["event_type"] is FilamentReconciliationEventType.REVERSAL:
                values["event_type"] = "PRINT_CONSUMPTION_REVERSAL"
                values["amount_g"] = amount
            else:
                values["event_type"] = "RECONCILIATION_SKIP"
                values["amount_g"] = Decimal("0")
            yield values

        calibration_statement = (
            select(
                literal("calibration").label("event_domain"), SpoolCalibration.id.label("event_id"),
                SpoolCalibration.spool_id, Spool.code.label("spool_code"),
                SpoolCalibration.event_type, SpoolCalibration.effective_at,
                SpoolCalibration.created_at, SpoolCalibration.adjustment_g.label("amount_g"),
                SpoolCalibration.previous_remaining_g.label("balance_before_g"),
                SpoolCalibration.new_remaining_g.label("balance_after_g"),
                literal(None).label("print_job_id"), literal(None).label("filament_usage_id"),
                SpoolCalibration.reversed_calibration_id.label("reversal_of_event_id"),
                literal(None).label("reason"), SpoolCalibration.note,
            )
            .select_from(SpoolCalibration)
            .join(Spool, Spool.id == SpoolCalibration.spool_id)
            .join(Material, Material.id == Spool.material_id)
            .join(Manufacturer, Manufacturer.id == Spool.manufacturer_id)
            .where(*self.analytics.date_conditions(SpoolCalibration.effective_at), *self.analytics.spool_conditions())
            .order_by(SpoolCalibration.id)
        )
        for row in self._stream(calibration_statement):
            values = dict(row)
            values["event_type"] = "PHYSICAL_CALIBRATION" if values["event_type"] is CalibrationEventType.PHYSICAL_CALIBRATION else "CALIBRATION_REVERSAL"
            yield values

        previous = func.lag(WeightHistory.weight_g).over(
            partition_by=WeightHistory.spool_id,
            order_by=(WeightHistory.created_at, WeightHistory.id),
        ).label("balance_before_g")
        weight_statement = (
            select(
                literal("weight_history").label("event_domain"), WeightHistory.id.label("event_id"),
                WeightHistory.spool_id, Spool.code.label("spool_code"), WeightHistory.source.label("event_type"),
                WeightHistory.created_at.label("effective_at"), WeightHistory.created_at,
                (WeightHistory.weight_g - previous).label("amount_g"), previous,
                WeightHistory.weight_g.label("balance_after_g"), literal(None).label("print_job_id"),
                literal(None).label("filament_usage_id"), literal(None).label("reversal_of_event_id"),
                literal(None).label("reason"), WeightHistory.notes.label("note"),
            )
            .select_from(WeightHistory)
            .join(Spool, Spool.id == WeightHistory.spool_id)
            .join(Material, Material.id == Spool.material_id)
            .join(Manufacturer, Manufacturer.id == Spool.manufacturer_id)
            .where(*self.analytics.date_conditions(WeightHistory.created_at), *self.analytics.spool_conditions())
            .order_by(WeightHistory.spool_id, WeightHistory.created_at, WeightHistory.id)
        )
        for row in self._stream(weight_statement):
            values = dict(row)
            values["event_type"] = f"WEIGHT_{_enum_value(values['event_type'])}"
            yield values

    def _rows_calibrations(self) -> Iterator[Mapping[str, Any]]:
        statement = (
            select(
                SpoolCalibration.id.label("calibration_id"), SpoolCalibration.spool_id,
                Spool.code.label("spool_code"), SpoolCalibration.event_type,
                SpoolCalibration.effective_at.label("calibrated_at"), SpoolCalibration.measured_total_g,
                SpoolCalibration.tare_g_used.label("tare_g"),
                SpoolCalibration.calculated_filament_g.label("physical_filament_g"),
                SpoolCalibration.previous_remaining_g.label("expected_before_g"),
                SpoolCalibration.adjustment_g, SpoolCalibration.new_remaining_g.label("balance_after_g"),
                SpoolCalibration.tare_source_used.label("tare_source"),
                SpoolCalibration.tare_confidence_used.label("tare_confidence"),
                SpoolCalibration.tare_profile_id, TareProfile.name.label("tare_profile"),
                SpoolCalibration.note, SpoolCalibration.reversed_calibration_id.label("reversal_of_calibration_id"),
                SpoolCalibration.reversed_at, SpoolCalibration.created_at,
            )
            .select_from(SpoolCalibration)
            .join(Spool, Spool.id == SpoolCalibration.spool_id)
            .join(Material, Material.id == Spool.material_id)
            .join(Manufacturer, Manufacturer.id == Spool.manufacturer_id)
            .outerjoin(TareProfile, TareProfile.id == SpoolCalibration.tare_profile_id)
            .where(*self.analytics.date_conditions(SpoolCalibration.effective_at), *self.analytics.spool_conditions())
            .order_by(SpoolCalibration.effective_at, SpoolCalibration.id)
        )
        yield from self._stream(statement)

    def _rows_consumption_over_time(self) -> Iterator[Mapping[str, Any]]:
        result = self.analytics.consumption_over_time(self.bucket)
        yield from (point.model_dump() for point in result.points)

    def _rows_top_spools(self) -> Iterator[Mapping[str, Any]]:
        for rank, row in enumerate(self.analytics.top_spools(10), 1):
            yield {"rank": rank, **row.model_dump()}

    def _rows_consumption_by_material(self) -> Iterator[Mapping[str, Any]]:
        for rank, row in enumerate(self.analytics.consumption_by_material(), 1):
            values = row.model_dump()
            yield {"rank": rank, "material": values.pop("name"), **values}

    def _rows_consumption_by_brand(self) -> Iterator[Mapping[str, Any]]:
        for rank, row in enumerate(self.analytics.consumption_by_brand(), 1):
            values = row.model_dump()
            yield {"rank": rank, "brand": values.pop("name"), **values}

    def _rows_inventory_by_material(self) -> Iterator[Mapping[str, Any]]:
        for rank, row in enumerate(self.analytics.inventory_by_material(), 1):
            yield {"rank": rank, **row.model_dump()}

    def _rows_purchases_by_store(self) -> Iterator[Mapping[str, Any]]:
        result = self.analytics.purchases_by_store(10)
        for rank, row in enumerate(result.by_spend, 1):
            yield {"ranking_type": "spend", "rank": rank, **row.model_dump(), "spool_count": None}
        for rank, row in enumerate(result.by_spool_count, 1):
            yield {"ranking_type": "spool_count", "rank": rank, **row.model_dump(), "currency": None, "amount": None, "priced_spool_count": None}

    def _rows_purchase_spend_over_time(self) -> Iterator[Mapping[str, Any]]:
        result = self.analytics.purchase_spend_over_time(self.bucket)
        yield from (point.model_dump() for point in result.points)

    def _rows_print_outcomes(self) -> Iterator[Mapping[str, Any]]:
        result = self.analytics.print_outcomes()
        for outcome in ("completed", "failed", "cancelled", "unknown_terminal"):
            yield {"outcome": outcome, "count": getattr(result, outcome), "success_rate_percentage": result.success_rate_percentage}

    def _rows_print_activity(self) -> Iterator[Mapping[str, Any]]:
        result = self.analytics.print_activity(self.bucket)
        seconds = {row.period: row.count for row in result.printing_seconds_by_period}
        completed = {row.period: row.count for row in result.completed_prints_by_period}
        for period in sorted(seconds.keys() | completed.keys()):
            yield {"period": period, "printing_seconds": seconds.get(period, 0), "completed_print_count": completed.get(period, 0)}

    def _rows_largest_consuming_prints(self) -> Iterator[Mapping[str, Any]]:
        for rank, row in enumerate(self.analytics.top_consuming_prints(5), 1):
            yield {"rank": rank, **row.model_dump()}


def _drain(buffer: StringIO) -> bytes:
    value = buffer.getvalue().encode("utf-8")
    buffer.seek(0)
    buffer.truncate(0)
    return value


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, StrEnum) else value


def _csv_value(value: Any, *, text: bool) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = normalize_utc(value).isoformat()
    elif isinstance(value, date):
        value = value.isoformat()
    elif isinstance(value, Decimal):
        value = format(value, "f")
    elif isinstance(value, bool):
        value = "true" if value else "false"
    else:
        value = str(_enum_value(value))
    if text and value.lstrip(" \t\r\n")[:1] in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value
