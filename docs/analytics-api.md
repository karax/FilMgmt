# Analytics API semantics

Wave 6A exposes deterministic, read-only analytics under `/api/analytics`. The
dashboard is intentionally compact; chart-sized datasets remain in dedicated
series and ranking endpoints so a future dashboard does not over-fetch.

## Canonical sources

- Confirmed filament consumption is the sum of active
  `print_job_filament_reconciliations` rows whose structured event type is
  `CONSUMPTION` and whose `reversed_at` is null.
- Slicer estimates, skipped usages, reconciliation reversals, weight-history
  corrections, and physical calibration events never count as consumption.
- Every confirmed line counts independently, including a confirmed line on a
  partially reconciled multi-material print.
- Consumption, print outcomes, observed print duration, and print counts use
  `PrintJob.started_at`. Reconciliation creation time is never the print date.
- Purchases use `Spool.purchase_date`; missing dates are never inferred from
  `created_at`.
- Current inventory and pending reconciliation are current snapshots. They are
  not restricted by the selected historical date range.

## Date ranges and filters

Every endpoint has a range. The default is `last_30_days`; callers may pass:

`last_7_days`, `last_30_days`, `last_90_days`, `this_year`,
`last_12_months`, `all_time`, or `custom`.

Custom ranges require inclusive local `from` and `to` dates. `timezone` is an
IANA name and defaults to `UTC`. Boundaries are converted to UTC before querying
the UTC timestamps stored by the application. Datetime series are first
aggregated by UTC hour in SQLite and then rebucketed in the requested timezone,
which preserves local midnight and daylight-saving boundaries without loading
individual ledger rows.

Optional exact, case-insensitive filters are `material`, `brand`, `store`, and
`spool_id`. Print-level metrics with a dimension filter include prints having at
least one active confirmed consumption line matching that dimension.

Rows with no print timestamp can be included in all-time totals but cannot be
placed on a time series; the consumption series reports them separately as
`unbucketed_consumption_g`. Purchase series use the equivalent
`unbucketed_amounts` for missing purchase dates.

## Metric definitions

- Successful/completed prints combine the actual legacy `SUCCESS` and current
  `COMPLETED` statuses.
- Success rate is `completed / (completed + failed + cancelled)`. Active and
  unknown-terminal jobs are excluded. A zero denominator returns `null`.
- Actual printing time uses `duration_seconds` only. Missing observed duration
  is excluded and reported through duration coverage; slicer-estimated duration
  is never substituted.
- Active inventory means a non-archived spool in `SEALED`, `OPEN`, `IN_USE`,
  `LOW`, or `NEEDS_DRYING`. Empty and archived counts are reported separately.
- Material cost uses `purchase_price / initial_filament_weight_g`, multiplied
  by active confirmed consumption. Missing price is unknown, not free.
  Coverage is confirmed grams with usable price metadata divided by all
  confirmed grams.
- Money is grouped by the spool's stored currency. Different currencies are
  never summed or ranked against one another. The dashboard returns one highest
  spend store per currency.
- Blank brand/store metadata is returned in an explicit `Unknown` bucket.

Decimal grams are serialized to three places, currency amounts to two places,
and percentages to two places, following the API's existing Decimal-as-string
JSON convention.

## Endpoints

- `GET /api/analytics/dashboard`
- `GET /api/analytics/consumption-over-time?bucket=day|week|month`
- `GET /api/analytics/top-spools?limit=10`
- `GET /api/analytics/consumption-by-material`
- `GET /api/analytics/consumption-by-brand`
- `GET /api/analytics/inventory-by-material`
- `GET /api/analytics/purchases-by-store?limit=10`
- `GET /api/analytics/purchase-spend-over-time?bucket=day|week|month`
- `GET /api/analytics/print-activity?bucket=day|week|month`
- `GET /api/analytics/top-consuming-prints?limit=10`

All analytics operations are GET-only and never create reconciliation,
inventory, calibration, or weight-history events. The Wave 6C CSV endpoint
reuses these same semantics; see [CSV export and data portability](csv-export.md).
There is no analytics persistence, FX conversion, or AI recommendation layer.
