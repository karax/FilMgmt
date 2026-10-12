from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import UtcDatetime


class AnalyticsRangePreset(StrEnum):
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    THIS_YEAR = "this_year"
    LAST_12_MONTHS = "last_12_months"
    ALL_TIME = "all_time"
    CUSTOM = "custom"


class AnalyticsBucket(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class AnalyticsPeriodRead(BaseModel):
    preset: AnalyticsRangePreset
    from_: UtcDatetime | None = Field(serialization_alias="from")
    to: UtcDatetime
    timezone: str
    date_field: str


class MoneyAmountRead(BaseModel):
    currency: str
    amount: Decimal


class ConsumptionSummaryRead(BaseModel):
    confirmed_g: Decimal
    confirmed_kg: Decimal
    estimated_costs: list[MoneyAmountRead]
    confirmed_g_with_known_cost: Decimal
    cost_coverage_percentage: Decimal | None


class InventorySummaryRead(BaseModel):
    active_spool_count: int
    current_remaining_g: Decimal
    empty_spool_count: int
    archived_spool_count: int


class ReconciliationSummaryRead(BaseModel):
    pending_print_count: int
    pending_filament_usage_count: int


class PrintOutcomesRead(BaseModel):
    completed: int
    failed: int
    cancelled: int
    unknown_terminal: int
    success_rate_percentage: Decimal | None


class PrintingActivitySummaryRead(BaseModel):
    actual_printing_seconds: int
    actual_printing_hours: Decimal
    jobs_with_actual_duration: int
    total_terminal_jobs: int
    duration_coverage_percentage: Decimal | None


class TimeSeriesCountPoint(BaseModel):
    period: str
    count: int


class ConsumptionSeriesPoint(BaseModel):
    period: str
    consumption_g: Decimal


class ConsumptionSeriesRead(BaseModel):
    period: AnalyticsPeriodRead
    bucket: AnalyticsBucket
    points: list[ConsumptionSeriesPoint]
    unbucketed_consumption_g: Decimal


class PurchaseSpendSeriesPoint(BaseModel):
    period: str
    currency: str
    amount: Decimal


class PurchaseSpendSeriesRead(BaseModel):
    period: AnalyticsPeriodRead
    bucket: AnalyticsBucket
    points: list[PurchaseSpendSeriesPoint]
    unbucketed_amounts: list[MoneyAmountRead]


class SpoolConsumptionRankRead(BaseModel):
    spool_id: int
    code: str
    display_name: str
    brand: str
    material: str
    color: str
    consumption_g: Decimal
    print_count: int


class DimensionConsumptionRead(BaseModel):
    name: str
    consumption_g: Decimal
    print_count: int


class InventoryByMaterialRead(BaseModel):
    material: str
    remaining_g: Decimal
    spool_count: int


class StoreSpendRead(BaseModel):
    store: str
    currency: str
    amount: Decimal
    priced_spool_count: int


class StoreSpoolCountRead(BaseModel):
    store: str
    spool_count: int


class PurchasesByStoreRead(BaseModel):
    period: AnalyticsPeriodRead
    by_spend: list[StoreSpendRead]
    by_spool_count: list[StoreSpoolCountRead]


class TopPrintRead(BaseModel):
    print_job_id: int
    name: str
    started_at: UtcDatetime | None
    consumption_g: Decimal


class PrintActivityRead(BaseModel):
    period: AnalyticsPeriodRead
    bucket: AnalyticsBucket
    outcomes: PrintOutcomesRead
    activity: PrintingActivitySummaryRead
    printing_seconds_by_period: list[TimeSeriesCountPoint]
    completed_prints_by_period: list[TimeSeriesCountPoint]


class DashboardHighlightsRead(BaseModel):
    most_used_spool: SpoolConsumptionRankRead | None
    most_consumed_material: DimensionConsumptionRead | None
    most_consumed_brand: DimensionConsumptionRead | None
    highest_spend_stores_by_currency: list[StoreSpendRead]
    most_spools_store: StoreSpoolCountRead | None


class DashboardPrintingRead(PrintOutcomesRead, PrintingActivitySummaryRead):
    pass


class AnalyticsDashboardRead(BaseModel):
    period: AnalyticsPeriodRead
    consumption: ConsumptionSummaryRead
    printing: DashboardPrintingRead
    inventory: InventorySummaryRead
    reconciliation: ReconciliationSummaryRead
    highlights: DashboardHighlightsRead
