from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Select, and_, case, distinct, exists, func, literal, or_, select
from sqlalchemy.orm import Session

from app.models import (
    FilamentReconciliationEventType,
    Manufacturer,
    Material,
    PrintJob,
    PrintJobEnrichmentStatus,
    PrintJobFilamentReconciliation,
    PrintJobFilamentUsage,
    PrintJobStatus,
    Spool,
    SpoolStatus,
)
from app.schemas.analytics import (
    AnalyticsBucket,
    AnalyticsDashboardRead,
    AnalyticsPeriodRead,
    AnalyticsRangePreset,
    ConsumptionSeriesPoint,
    ConsumptionSeriesRead,
    ConsumptionSummaryRead,
    DashboardHighlightsRead,
    DashboardPrintingRead,
    DimensionConsumptionRead,
    InventoryByMaterialRead,
    InventorySummaryRead,
    MoneyAmountRead,
    PrintActivityRead,
    PrintingActivitySummaryRead,
    PrintOutcomesRead,
    PurchaseSpendSeriesPoint,
    PurchaseSpendSeriesRead,
    PurchasesByStoreRead,
    ReconciliationSummaryRead,
    SpoolConsumptionRankRead,
    StoreSpendRead,
    StoreSpoolCountRead,
    TimeSeriesCountPoint,
    TopPrintRead,
)


GRAM_QUANTUM = Decimal("0.001")
MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")
UNKNOWN = "Unknown"

SUCCESS_STATUSES = {PrintJobStatus.SUCCESS, PrintJobStatus.COMPLETED}
TERMINAL_STATUSES = {
    *SUCCESS_STATUSES,
    PrintJobStatus.FAILED,
    PrintJobStatus.CANCELLED,
    PrintJobStatus.UNKNOWN_TERMINAL,
}
RESOLUTION_EVENT_TYPES = {
    FilamentReconciliationEventType.CONSUMPTION,
    FilamentReconciliationEventType.SKIP,
}
ACTIVE_INVENTORY_STATUSES = {
    SpoolStatus.SEALED,
    SpoolStatus.OPEN,
    SpoolStatus.IN_USE,
    SpoolStatus.LOW,
    SpoolStatus.NEEDS_DRYING,
}


class AnalyticsRangeError(ValueError):
    pass


@dataclass(frozen=True)
class AnalyticsFilters:
    material: str | None = None
    brand: str | None = None
    store: str | None = None
    spool_id: int | None = None


@dataclass(frozen=True)
class AnalyticsDateRange:
    preset: AnalyticsRangePreset
    start_utc: datetime | None
    end_utc: datetime
    timezone: ZoneInfo

    @classmethod
    def resolve(
        cls,
        preset: AnalyticsRangePreset,
        from_date: date | None,
        to_date: date | None,
        timezone_name: str,
        *,
        now: datetime | None = None,
    ) -> AnalyticsDateRange:
        try:
            requested_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise AnalyticsRangeError("Unknown IANA timezone.") from error

        current = (now or datetime.now(UTC)).astimezone(requested_timezone)
        today = current.date()
        if preset is AnalyticsRangePreset.CUSTOM:
            if from_date is None or to_date is None:
                raise AnalyticsRangeError("Custom ranges require both from and to dates.")
            if from_date > to_date:
                raise AnalyticsRangeError("from must be on or before to.")
            start_date = from_date
            end_date = to_date + timedelta(days=1)
        else:
            if from_date is not None or to_date is not None:
                raise AnalyticsRangeError("from and to may only be used with range=custom.")
            if preset is AnalyticsRangePreset.ALL_TIME:
                return cls(preset, None, current.astimezone(UTC), requested_timezone)
            if preset is AnalyticsRangePreset.LAST_7_DAYS:
                start_date = today - timedelta(days=6)
            elif preset is AnalyticsRangePreset.LAST_30_DAYS:
                start_date = today - timedelta(days=29)
            elif preset is AnalyticsRangePreset.LAST_90_DAYS:
                start_date = today - timedelta(days=89)
            elif preset is AnalyticsRangePreset.THIS_YEAR:
                start_date = date(today.year, 1, 1)
            elif preset is AnalyticsRangePreset.LAST_12_MONTHS:
                month_index = today.year * 12 + today.month - 12
                start_date = date(month_index // 12, month_index % 12 + 1, 1)
            else:  # pragma: no cover - enum validation owns this branch
                raise AnalyticsRangeError("Unsupported date range.")
            end_date = today + timedelta(days=1)

        start_local = datetime.combine(start_date, time.min, requested_timezone)
        end_local = datetime.combine(end_date, time.min, requested_timezone)
        return cls(
            preset,
            start_local.astimezone(UTC),
            end_local.astimezone(UTC),
            requested_timezone,
        )

    def read(self, date_field: str) -> AnalyticsPeriodRead:
        return AnalyticsPeriodRead(
            preset=self.preset,
            from_=self.start_utc,
            to=self.end_utc,
            timezone=self.timezone.key,
            date_field=date_field,
        )


class AnalyticsService:
    """Read-only SQL aggregation over canonical inventory and print records."""

    def __init__(
        self,
        db: Session,
        date_range: AnalyticsDateRange,
        filters: AnalyticsFilters | None = None,
    ) -> None:
        self.db = db
        self.date_range = date_range
        self.filters = filters or AnalyticsFilters()

    def dashboard(self) -> AnalyticsDashboardRead:
        outcomes = self.print_outcomes()
        activity = self.printing_activity_summary()
        top_spools = self.top_spools(limit=1)
        materials = self.consumption_by_material(limit=1)
        brands = self.consumption_by_brand(limit=1)
        purchases = self.purchases_by_store(limit=100)
        highest_by_currency: list[StoreSpendRead] = []
        seen_currencies: set[str] = set()
        for row in purchases.by_spend:
            if row.currency not in seen_currencies:
                highest_by_currency.append(row)
                seen_currencies.add(row.currency)

        return AnalyticsDashboardRead(
            period=self.date_range.read("print_jobs.started_at"),
            consumption=self.consumption_summary(),
            printing=DashboardPrintingRead(
                **outcomes.model_dump(),
                **activity.model_dump(),
            ),
            inventory=self.inventory_summary(),
            reconciliation=self.pending_reconciliation(),
            highlights=DashboardHighlightsRead(
                most_used_spool=top_spools[0] if top_spools else None,
                most_consumed_material=materials[0] if materials else None,
                most_consumed_brand=brands[0] if brands else None,
                highest_spend_stores_by_currency=highest_by_currency,
                most_spools_store=(
                    purchases.by_spool_count[0] if purchases.by_spool_count else None
                ),
            ),
        )

    def consumption_summary(self) -> ConsumptionSummaryRead:
        total = _decimal(
            self.db.scalar(
                self._consumption_select(func.sum(PrintJobFilamentReconciliation.amount_g))
            )
        )
        cost_rows = self.db.execute(
            self._consumption_select(
                Spool.id,
                Spool.purchase_price,
                Spool.initial_filament_weight_g,
                Spool.currency,
                func.sum(PrintJobFilamentReconciliation.amount_g).label("consumption_g"),
            ).group_by(
                Spool.id,
                Spool.purchase_price,
                Spool.initial_filament_weight_g,
                Spool.currency,
            )
        ).all()
        known_grams = Decimal("0")
        costs: dict[str, Decimal] = defaultdict(Decimal)
        for row in cost_rows:
            consumed = _decimal(row.consumption_g)
            if row.purchase_price is None or row.initial_filament_weight_g is None:
                continue
            purchased_g = _decimal(row.initial_filament_weight_g)
            if purchased_g <= 0:
                continue
            known_grams += consumed
            costs[row.currency] += consumed * _decimal(row.purchase_price) / purchased_g

        return ConsumptionSummaryRead(
            confirmed_g=_grams(total),
            confirmed_kg=(total / Decimal("1000")).quantize(GRAM_QUANTUM),
            estimated_costs=[
                MoneyAmountRead(currency=currency, amount=_money(amount))
                for currency, amount in sorted(costs.items())
            ],
            confirmed_g_with_known_cost=_grams(known_grams),
            cost_coverage_percentage=_percentage(known_grams, total),
        )

    def consumption_over_time(self, bucket: AnalyticsBucket) -> ConsumptionSeriesRead:
        hour = func.strftime(
            "%Y-%m-%dT%H:00:00", PrintJob.started_at
        ).label("utc_hour")
        query = self._consumption_select(
            hour,
            func.sum(PrintJobFilamentReconciliation.amount_g).label("value"),
        ).where(PrintJob.started_at.is_not(None)).group_by(hour)
        rows = self.db.execute(query).all()
        totals = self._rebucket_datetime_rows(rows, bucket, decimal_values=True)

        unbucketed = Decimal("0")
        if self.date_range.preset is AnalyticsRangePreset.ALL_TIME:
            unbucketed = _decimal(
                self.db.scalar(
                    self._consumption_select(
                        func.sum(PrintJobFilamentReconciliation.amount_g)
                    ).where(PrintJob.started_at.is_(None))
                )
            )
        return ConsumptionSeriesRead(
            period=self.date_range.read("print_jobs.started_at"),
            bucket=bucket,
            points=[
                ConsumptionSeriesPoint(period=period, consumption_g=_grams(value))
                for period, value in sorted(totals.items())
            ],
            unbucketed_consumption_g=_grams(unbucketed),
        )

    def top_spools(self, limit: int = 10) -> list[SpoolConsumptionRankRead]:
        consumption = func.sum(PrintJobFilamentReconciliation.amount_g).label(
            "consumption_g"
        )
        count = func.count(distinct(PrintJobFilamentReconciliation.print_job_id)).label(
            "print_count"
        )
        rows = self.db.execute(
            self._consumption_select(
                Spool.id,
                Spool.code,
                Spool.display_name,
                Spool.product_name,
                Spool.color_name,
                Material.name.label("material"),
                Manufacturer.name.label("brand"),
                consumption,
                count,
            )
            .group_by(
                Spool.id,
                Spool.code,
                Spool.display_name,
                Spool.product_name,
                Spool.color_name,
                Material.name,
                Manufacturer.name,
            )
            .order_by(consumption.desc(), Spool.id)
            .limit(limit)
        ).all()
        return [
            SpoolConsumptionRankRead(
                spool_id=row.id,
                code=row.code,
                display_name=row.display_name or row.product_name or row.code,
                brand=row.brand or UNKNOWN,
                material=row.material or UNKNOWN,
                color=row.color_name,
                consumption_g=_grams(row.consumption_g),
                print_count=row.print_count,
            )
            for row in rows
        ]

    def consumption_by_material(self, limit: int | None = None) -> list[DimensionConsumptionRead]:
        return self._consumption_by_dimension(Material.name, limit)

    def consumption_by_brand(self, limit: int | None = None) -> list[DimensionConsumptionRead]:
        return self._consumption_by_dimension(Manufacturer.name, limit)

    def inventory_summary(self) -> InventorySummaryRead:
        active_condition = and_(
            Spool.archived_at.is_(None),
            Spool.status.in_(ACTIVE_INVENTORY_STATUSES),
        )
        active_count, remaining = self.db.execute(
            self._spool_select(
                func.count(Spool.id),
                func.sum(Spool.current_filament_weight_g),
            ).where(active_condition)
        ).one()
        empty_count = self.db.scalar(
            self._spool_select(func.count(Spool.id)).where(
                Spool.archived_at.is_(None), Spool.status == SpoolStatus.EMPTY
            )
        )
        archived_count = self.db.scalar(
            self._spool_select(func.count(Spool.id)).where(
                or_(Spool.archived_at.is_not(None), Spool.status == SpoolStatus.ARCHIVED)
            )
        )
        return InventorySummaryRead(
            active_spool_count=active_count or 0,
            current_remaining_g=_grams(_decimal(remaining)),
            empty_spool_count=empty_count or 0,
            archived_spool_count=archived_count or 0,
        )

    def inventory_by_material(self) -> list[InventoryByMaterialRead]:
        remaining = func.sum(Spool.current_filament_weight_g).label("remaining_g")
        rows = self.db.execute(
            self._spool_select(
                Material.name.label("material"),
                remaining,
                func.count(Spool.id).label("spool_count"),
            )
            .where(
                Spool.archived_at.is_(None),
                Spool.status.in_(ACTIVE_INVENTORY_STATUSES),
            )
            .group_by(Material.name)
            .order_by(remaining.desc(), Material.name)
        ).all()
        return [
            InventoryByMaterialRead(
                material=row.material or UNKNOWN,
                remaining_g=_grams(row.remaining_g),
                spool_count=row.spool_count,
            )
            for row in rows
        ]

    def purchases_by_store(self, limit: int = 10) -> PurchasesByStoreRead:
        store = func.coalesce(func.nullif(func.trim(Spool.store_name), ""), UNKNOWN)
        spend = func.sum(Spool.purchase_price).label("amount")
        spend_rows = self.db.execute(
            self._purchase_select(
                store.label("store"),
                Spool.currency,
                spend,
                func.count(Spool.id).label("priced_spool_count"),
            )
            .where(Spool.purchase_price.is_not(None))
            .group_by(store, Spool.currency)
            .order_by(Spool.currency, spend.desc(), store)
            .limit(limit)
        ).all()
        spool_count = func.count(Spool.id).label("spool_count")
        count_rows = self.db.execute(
            self._purchase_select(store.label("store"), spool_count)
            .group_by(store)
            .order_by(spool_count.desc(), store)
            .limit(limit)
        ).all()
        return PurchasesByStoreRead(
            period=self.date_range.read("spools.purchase_date"),
            by_spend=[
                StoreSpendRead(
                    store=row.store,
                    currency=row.currency,
                    amount=_money(row.amount),
                    priced_spool_count=row.priced_spool_count,
                )
                for row in spend_rows
            ],
            by_spool_count=[
                StoreSpoolCountRead(store=row.store, spool_count=row.spool_count)
                for row in count_rows
            ],
        )

    def purchase_spend_over_time(self, bucket: AnalyticsBucket) -> PurchaseSpendSeriesRead:
        period_expression = self._date_bucket(Spool.purchase_date, bucket).label("period")
        amount = func.sum(Spool.purchase_price).label("amount")
        rows = self.db.execute(
            self._purchase_select(period_expression, Spool.currency, amount)
            .where(Spool.purchase_date.is_not(None), Spool.purchase_price.is_not(None))
            .group_by(period_expression, Spool.currency)
            .order_by(period_expression, Spool.currency)
        ).all()
        unbucketed: list[MoneyAmountRead] = []
        if self.date_range.preset is AnalyticsRangePreset.ALL_TIME:
            missing_rows = self.db.execute(
                self._purchase_select(Spool.currency, amount)
                .where(Spool.purchase_date.is_(None), Spool.purchase_price.is_not(None))
                .group_by(Spool.currency)
                .order_by(Spool.currency)
            ).all()
            unbucketed = [
                MoneyAmountRead(currency=row.currency, amount=_money(row.amount))
                for row in missing_rows
            ]
        return PurchaseSpendSeriesRead(
            period=self.date_range.read("spools.purchase_date"),
            bucket=bucket,
            points=[
                PurchaseSpendSeriesPoint(
                    period=row.period,
                    currency=row.currency,
                    amount=_money(row.amount),
                )
                for row in rows
            ],
            unbucketed_amounts=unbucketed,
        )

    def print_outcomes(self) -> PrintOutcomesRead:
        successful = func.sum(case((PrintJob.status.in_(SUCCESS_STATUSES), 1), else_=0))
        failed = func.sum(case((PrintJob.status == PrintJobStatus.FAILED, 1), else_=0))
        cancelled = func.sum(case((PrintJob.status == PrintJobStatus.CANCELLED, 1), else_=0))
        unknown = func.sum(
            case((PrintJob.status == PrintJobStatus.UNKNOWN_TERMINAL, 1), else_=0)
        )
        completed_value, failed_value, cancelled_value, unknown_value = self.db.execute(
            self._print_select(successful, failed, cancelled, unknown).where(
                PrintJob.status.in_(TERMINAL_STATUSES)
            )
        ).one()
        completed_count = int(completed_value or 0)
        failed_count = int(failed_value or 0)
        cancelled_count = int(cancelled_value or 0)
        denominator = completed_count + failed_count + cancelled_count
        return PrintOutcomesRead(
            completed=completed_count,
            failed=failed_count,
            cancelled=cancelled_count,
            unknown_terminal=int(unknown_value or 0),
            success_rate_percentage=(
                _percentage(Decimal(completed_count), Decimal(denominator))
                if denominator
                else None
            ),
        )

    def printing_activity_summary(self) -> PrintingActivitySummaryRead:
        duration_sum, duration_count, terminal_count = self.db.execute(
            self._print_select(
                func.sum(PrintJob.duration_seconds),
                func.count(PrintJob.duration_seconds),
                func.count(PrintJob.id),
            ).where(PrintJob.status.in_(TERMINAL_STATUSES))
        ).one()
        seconds = int(duration_sum or 0)
        jobs_with_duration = int(duration_count or 0)
        total_terminal = int(terminal_count or 0)
        return PrintingActivitySummaryRead(
            actual_printing_seconds=seconds,
            actual_printing_hours=(Decimal(seconds) / Decimal("3600")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            jobs_with_actual_duration=jobs_with_duration,
            total_terminal_jobs=total_terminal,
            duration_coverage_percentage=_percentage(
                Decimal(jobs_with_duration), Decimal(total_terminal)
            ),
        )

    def print_activity(self, bucket: AnalyticsBucket) -> PrintActivityRead:
        hour = func.strftime("%Y-%m-%dT%H:00:00", PrintJob.started_at).label(
            "utc_hour"
        )
        seconds_rows = self.db.execute(
            self._print_select(hour, func.sum(PrintJob.duration_seconds).label("value"))
            .where(
                PrintJob.status.in_(TERMINAL_STATUSES),
                PrintJob.started_at.is_not(None),
                PrintJob.duration_seconds.is_not(None),
            )
            .group_by(hour)
        ).all()
        completed_rows = self.db.execute(
            self._print_select(hour, func.count(PrintJob.id).label("value"))
            .where(
                PrintJob.status.in_(SUCCESS_STATUSES),
                PrintJob.started_at.is_not(None),
            )
            .group_by(hour)
        ).all()
        seconds = self._rebucket_datetime_rows(seconds_rows, bucket, decimal_values=False)
        completed = self._rebucket_datetime_rows(
            completed_rows, bucket, decimal_values=False
        )
        return PrintActivityRead(
            period=self.date_range.read("print_jobs.started_at"),
            bucket=bucket,
            outcomes=self.print_outcomes(),
            activity=self.printing_activity_summary(),
            printing_seconds_by_period=[
                TimeSeriesCountPoint(period=key, count=int(value))
                for key, value in sorted(seconds.items())
            ],
            completed_prints_by_period=[
                TimeSeriesCountPoint(period=key, count=int(value))
                for key, value in sorted(completed.items())
            ],
        )

    def pending_reconciliation(self) -> ReconciliationSummaryRead:
        active_resolution = exists(
            select(literal(1)).where(
                PrintJobFilamentReconciliation.filament_usage_id
                == PrintJobFilamentUsage.id,
                PrintJobFilamentReconciliation.event_type.in_(RESOLUTION_EVENT_TYPES),
                PrintJobFilamentReconciliation.reversed_at.is_(None),
            )
        )
        base = (
            select(
                func.count(distinct(PrintJobFilamentUsage.print_job_id)),
                func.count(PrintJobFilamentUsage.id),
            )
            .select_from(PrintJobFilamentUsage)
            .join(PrintJob, PrintJob.id == PrintJobFilamentUsage.print_job_id)
            .where(
                PrintJob.status.in_(TERMINAL_STATUSES),
                PrintJob.enrichment_status == PrintJobEnrichmentStatus.ENRICHED,
                ~active_resolution,
            )
        )
        print_count, usage_count = self.db.execute(base).one()
        return ReconciliationSummaryRead(
            pending_print_count=print_count or 0,
            pending_filament_usage_count=usage_count or 0,
        )

    def top_consuming_prints(self, limit: int = 10) -> list[TopPrintRead]:
        consumption = func.sum(PrintJobFilamentReconciliation.amount_g).label(
            "consumption_g"
        )
        rows = self.db.execute(
            self._consumption_select(
                PrintJob.id,
                PrintJob.name,
                PrintJob.gcode_file,
                PrintJob.started_at,
                consumption,
            )
            .group_by(
                PrintJob.id,
                PrintJob.name,
                PrintJob.gcode_file,
                PrintJob.started_at,
            )
            .order_by(consumption.desc(), PrintJob.id)
            .limit(limit)
        ).all()
        return [
            TopPrintRead(
                print_job_id=row.id,
                name=row.name or row.gcode_file or f"Print #{row.id}",
                started_at=row.started_at,
                consumption_g=_grams(row.consumption_g),
            )
            for row in rows
        ]

    def confirmed_consumption_select(self, *columns) -> Select:
        """Expose the canonical active-consumption query for read-only exports.

        Keeping this query in AnalyticsService guarantees CSV rows use the same
        reversal, print-date, and dimension-filter semantics as dashboard totals.
        """
        return self._consumption_select(*columns).join(
            PrintJobFilamentUsage,
            PrintJobFilamentUsage.id
            == PrintJobFilamentReconciliation.filament_usage_id,
        )

    def spool_select(self, *columns) -> Select:
        """Return a spool query with the active analytics dimension filters."""
        return self._spool_select(*columns)

    def purchase_select(self, *columns) -> Select:
        """Return a purchase query with canonical purchase-date filtering."""
        return self._purchase_select(*columns)

    def print_select(self, *columns) -> Select:
        """Return a PrintJob query with canonical date and dimension filtering."""
        return self._print_select(*columns)

    def date_conditions(self, column) -> list:
        """Return the selected UTC date boundaries for a timestamp column."""
        return self._date_conditions(column)

    def spool_conditions(self) -> list:
        """Return canonical material, brand, store, and physical-spool filters."""
        return self._spool_conditions()

    def _consumption_by_dimension(
        self, dimension, limit: int | None
    ) -> list[DimensionConsumptionRead]:
        name = func.coalesce(func.nullif(func.trim(dimension), ""), UNKNOWN).label(
            "name"
        )
        consumption = func.sum(PrintJobFilamentReconciliation.amount_g).label(
            "consumption_g"
        )
        count = func.count(distinct(PrintJobFilamentReconciliation.print_job_id)).label(
            "print_count"
        )
        query = (
            self._consumption_select(name, consumption, count)
            .group_by(name)
            .order_by(consumption.desc(), name)
        )
        if limit is not None:
            query = query.limit(limit)
        rows = self.db.execute(query).all()
        return [
            DimensionConsumptionRead(
                name=row.name,
                consumption_g=_grams(row.consumption_g),
                print_count=row.print_count,
            )
            for row in rows
        ]

    def _consumption_select(self, *columns) -> Select:
        query = (
            select(*columns)
            .select_from(PrintJobFilamentReconciliation)
            .join(
                PrintJob,
                PrintJob.id == PrintJobFilamentReconciliation.print_job_id,
            )
            .join(Spool, Spool.id == PrintJobFilamentReconciliation.spool_id)
            .join(Material, Material.id == Spool.material_id)
            .join(Manufacturer, Manufacturer.id == Spool.manufacturer_id)
            .where(
                PrintJobFilamentReconciliation.event_type
                == FilamentReconciliationEventType.CONSUMPTION,
                PrintJobFilamentReconciliation.reversed_at.is_(None),
                *self._date_conditions(PrintJob.started_at),
                *self._spool_conditions(),
            )
        )
        return query

    def _spool_select(self, *columns) -> Select:
        return (
            select(*columns)
            .select_from(Spool)
            .join(Material, Material.id == Spool.material_id)
            .join(Manufacturer, Manufacturer.id == Spool.manufacturer_id)
            .where(*self._spool_conditions())
        )

    def _purchase_select(self, *columns) -> Select:
        return self._spool_select(*columns).where(
            *self._purchase_date_conditions()
        )

    def _print_select(self, *columns) -> Select:
        query = select(*columns).select_from(PrintJob).where(
            *self._date_conditions(PrintJob.started_at)
        )
        dimension_filter = self._print_dimension_filter()
        if dimension_filter is not None:
            query = query.where(dimension_filter)
        return query

    def _spool_conditions(self) -> list:
        conditions = []
        if self.filters.material:
            conditions.append(func.lower(Material.name) == self.filters.material.lower())
        if self.filters.brand:
            conditions.append(
                func.lower(Manufacturer.name) == self.filters.brand.lower()
            )
        if self.filters.store:
            conditions.append(
                func.lower(func.coalesce(Spool.store_name, UNKNOWN))
                == self.filters.store.lower()
            )
        if self.filters.spool_id is not None:
            conditions.append(Spool.id == self.filters.spool_id)
        return conditions

    def _print_dimension_filter(self):
        if not any(
            (
                self.filters.material,
                self.filters.brand,
                self.filters.store,
                self.filters.spool_id,
            )
        ):
            return None
        return exists(
            select(literal(1))
            .select_from(PrintJobFilamentReconciliation)
            .join(Spool, Spool.id == PrintJobFilamentReconciliation.spool_id)
            .join(Material, Material.id == Spool.material_id)
            .join(Manufacturer, Manufacturer.id == Spool.manufacturer_id)
            .where(
                PrintJobFilamentReconciliation.print_job_id == PrintJob.id,
                PrintJobFilamentReconciliation.event_type
                == FilamentReconciliationEventType.CONSUMPTION,
                PrintJobFilamentReconciliation.reversed_at.is_(None),
                *self._spool_conditions(),
            )
        )

    def _date_conditions(self, column) -> list:
        if self.date_range.preset is AnalyticsRangePreset.ALL_TIME:
            return []
        return [
            column.is_not(None),
            column >= self.date_range.start_utc,
            column < self.date_range.end_utc,
        ]

    def _purchase_date_conditions(self) -> list:
        if self.date_range.preset is AnalyticsRangePreset.ALL_TIME:
            return []
        assert self.date_range.start_utc is not None
        start_date = self.date_range.start_utc.astimezone(
            self.date_range.timezone
        ).date()
        end_date = self.date_range.end_utc.astimezone(
            self.date_range.timezone
        ).date()
        return [
            Spool.purchase_date.is_not(None),
            Spool.purchase_date >= start_date,
            Spool.purchase_date < end_date,
        ]

    def _rebucket_datetime_rows(
        self,
        rows,
        bucket: AnalyticsBucket,
        *,
        decimal_values: bool,
    ) -> dict[str, Decimal | int]:
        totals: dict[str, Decimal | int] = defaultdict(
            Decimal if decimal_values else int
        )
        for row in rows:
            if row.utc_hour is None:
                continue
            utc_hour = datetime.fromisoformat(row.utc_hour).replace(tzinfo=UTC)
            local = utc_hour.astimezone(self.date_range.timezone)
            label = _datetime_bucket_label(local, bucket)
            value = _decimal(row.value) if decimal_values else int(row.value or 0)
            totals[label] += value
        return totals

    @staticmethod
    def _date_bucket(column, bucket: AnalyticsBucket):
        if bucket is AnalyticsBucket.DAY:
            return func.strftime("%Y-%m-%d", column)
        if bucket is AnalyticsBucket.MONTH:
            return func.strftime("%Y-%m", column)
        return func.date(column, "weekday 0", "-6 days")


def _datetime_bucket_label(value: datetime, bucket: AnalyticsBucket) -> str:
    if bucket is AnalyticsBucket.DAY:
        return value.date().isoformat()
    if bucket is AnalyticsBucket.MONTH:
        return f"{value.year:04d}-{value.month:02d}"
    monday = value.date() - timedelta(days=value.weekday())
    return monday.isoformat()


def _decimal(value: object | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _grams(value: object | None) -> Decimal:
    return _decimal(value).quantize(GRAM_QUANTUM, rounding=ROUND_HALF_UP)


def _money(value: object | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _percentage(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return (numerator * Decimal("100") / denominator).quantize(
        PERCENT_QUANTUM, rounding=ROUND_HALF_UP
    )
