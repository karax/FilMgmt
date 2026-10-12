# CSV export and data portability

Wave 6C provides synchronous, read-only CSV downloads through
`GET /api/analytics/export`. The Analytics page exposes the allowlisted
datasets through **Export data**. There is no generic table, column, or SQL
export endpoint.

## Available datasets

Analytics datasets reuse `AnalyticsService` and the filters currently selected
on Analytics:

- confirmed consumption over time;
- top physical spools;
- consumption by material and brand;
- current inventory by material;
- purchases by store and purchase spending over time;
- print outcomes and observed printer activity;
- largest prints by active confirmed consumption.

Raw portability datasets are:

- physical spool inventory;
- PrintJob history;
- per-print sliced filament usage;
- active confirmed consumption;
- spool purchase metadata;
- the inventory ledger;
- physical calibration history.

Raw downloads can use the current supported Analytics filters or all data.
Spool inventory remains a current snapshot; a historical date range does not
turn it into historical inventory.

## Confirmed consumption versus the inventory ledger

These exports intentionally answer different questions:

- **Confirmed consumption** contains one row for each currently active
  reconciliation `CONSUMPTION` event. A reversed event disappears. If the
  usage is reconciled again, only the new active event appears. Skipped usage,
  pending usage, weight corrections, and physical calibrations never appear.
  `effective_print_date` is `PrintJob.started_at`, matching Analytics, while
  `reconciliation_date` separately preserves when confirmation happened.
- **Inventory ledger** is the full audit view. It preserves reconciliation
  consumption and reversal events, physical calibration and calibration
  reversal events, and the canonical `weight_history` balance checkpoints.
  `event_domain` identifies their source. Specialized lifecycle events and
  balance checkpoints are distinct audit records, so ledger rows should not be
  summed across domains as if they were one consumption series.

The filament-usage export keeps sliced estimates separate from confirmed
physical consumption and retains pending and explicitly skipped usages.

## Format guarantees

- UTF-8 with a BOM is used for reliable Excel and LibreOffice detection.
- The delimiter is a comma and quoting follows Python's standard `csv` Excel
  dialect.
- Headers are stable, English, machine-friendly `snake_case` values.
- Decimal values use a dot and contain no currency or unit suffix.
- Missing data is an empty cell, never an invented zero.
- Dates and timestamps use ISO 8601. Stored SQLite timestamps are interpreted
  as UTC and serialized with `+00:00`; purchase dates remain ISO dates.
- Text cells beginning with `=`, `+`, `-`, or `@` are prefixed with a single
  quote to prevent spreadsheet formula execution. Typed negative numeric
  values remain unchanged.
- Different currencies remain separate. No FX conversion is performed.

Responses stream rows in bounded batches and include `Content-Disposition`
with a sanitized descriptive filename. Export requests are GET-only and do not
create inventory, reconciliation, calibration, or weight-history events.

## API parameters

`dataset` is required and must be an allowlisted dataset. Standard Analytics
parameters are supported: `range`, `from`, `to`, `timezone`, `material`,
`brand`, `store`, `spool_id`, and `bucket`.

`scope=current` applies those semantics to raw datasets. `scope=all` removes
date and dimension filters for raw portability exports. Analytics datasets
always require `scope=current`, preventing an export from silently differing
from the dashboard selection.
