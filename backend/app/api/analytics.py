from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analytics import (
    AnalyticsBucket,
    AnalyticsDashboardRead,
    AnalyticsRangePreset,
    ConsumptionSeriesRead,
    DimensionConsumptionRead,
    InventoryByMaterialRead,
    PrintActivityRead,
    PurchaseSpendSeriesRead,
    PurchasesByStoreRead,
    SpoolConsumptionRankRead,
    TopPrintRead,
)
from app.services.analytics_service import (
    AnalyticsDateRange,
    AnalyticsFilters,
    AnalyticsRangeError,
    AnalyticsService,
)
from app.services.csv_export_service import (
    CsvExportService,
    ExportDataset,
    ExportScope,
    ExportScopeError,
)


router = APIRouter(prefix="/analytics", tags=["Analytics"])
DbSession = Annotated[Session, Depends(get_db)]


def get_analytics_service(
    db: DbSession,
    preset: Annotated[
        AnalyticsRangePreset,
        Query(alias="range", description="Historical analytics date range."),
    ] = AnalyticsRangePreset.LAST_30_DAYS,
    from_date: Annotated[
        date | None,
        Query(alias="from", description="Inclusive local date for a custom range."),
    ] = None,
    to_date: Annotated[
        date | None,
        Query(alias="to", description="Inclusive local date for a custom range."),
    ] = None,
    timezone: Annotated[
        str,
        Query(min_length=1, max_length=100, description="IANA timezone for date boundaries."),
    ] = "UTC",
    material: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    brand: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    store: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    spool_id: Annotated[int | None, Query(gt=0)] = None,
) -> AnalyticsService:
    try:
        date_range = AnalyticsDateRange.resolve(
            preset,
            from_date,
            to_date,
            timezone,
        )
    except AnalyticsRangeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    return AnalyticsService(
        db,
        date_range,
        AnalyticsFilters(
            material=material,
            brand=brand,
            store=store,
            spool_id=spool_id,
        ),
    )


Analytics = Annotated[AnalyticsService, Depends(get_analytics_service)]
Bucket = Annotated[AnalyticsBucket, Query()]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get("/dashboard", response_model=AnalyticsDashboardRead)
def dashboard(analytics: Analytics) -> AnalyticsDashboardRead:
    return analytics.dashboard()


@router.get("/consumption-over-time", response_model=ConsumptionSeriesRead)
def consumption_over_time(
    analytics: Analytics,
    bucket: Bucket = AnalyticsBucket.DAY,
) -> ConsumptionSeriesRead:
    return analytics.consumption_over_time(bucket)


@router.get("/top-spools", response_model=list[SpoolConsumptionRankRead])
def top_spools(
    analytics: Analytics,
    limit: Limit = 10,
) -> list[SpoolConsumptionRankRead]:
    return analytics.top_spools(limit)


@router.get("/consumption-by-material", response_model=list[DimensionConsumptionRead])
def consumption_by_material(analytics: Analytics) -> list[DimensionConsumptionRead]:
    return analytics.consumption_by_material()


@router.get("/consumption-by-brand", response_model=list[DimensionConsumptionRead])
def consumption_by_brand(analytics: Analytics) -> list[DimensionConsumptionRead]:
    return analytics.consumption_by_brand()


@router.get("/inventory-by-material", response_model=list[InventoryByMaterialRead])
def inventory_by_material(analytics: Analytics) -> list[InventoryByMaterialRead]:
    return analytics.inventory_by_material()


@router.get("/purchases-by-store", response_model=PurchasesByStoreRead)
def purchases_by_store(
    analytics: Analytics,
    limit: Limit = 10,
) -> PurchasesByStoreRead:
    return analytics.purchases_by_store(limit)


@router.get("/purchase-spend-over-time", response_model=PurchaseSpendSeriesRead)
def purchase_spend_over_time(
    analytics: Analytics,
    bucket: Bucket = AnalyticsBucket.MONTH,
) -> PurchaseSpendSeriesRead:
    return analytics.purchase_spend_over_time(bucket)


@router.get("/print-activity", response_model=PrintActivityRead)
def print_activity(
    analytics: Analytics,
    bucket: Bucket = AnalyticsBucket.DAY,
) -> PrintActivityRead:
    return analytics.print_activity(bucket)


@router.get("/top-consuming-prints", response_model=list[TopPrintRead])
def top_consuming_prints(
    analytics: Analytics,
    limit: Limit = 10,
) -> list[TopPrintRead]:
    return analytics.top_consuming_prints(limit)


@router.get("/export", response_class=StreamingResponse)
def export_csv(
    analytics: Analytics,
    dataset: Annotated[ExportDataset, Query(description="Allowlisted CSV dataset.")],
    scope: Annotated[ExportScope, Query(description="Current filters or all raw data.")] = ExportScope.CURRENT,
    bucket: Bucket = AnalyticsBucket.DAY,
) -> StreamingResponse:
    try:
        export = CsvExportService(
            analytics.db,
            analytics,
            dataset,
            scope,
            bucket,
        ).build()
    except ExportScopeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    return StreamingResponse(
        export.stream(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{export.filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
