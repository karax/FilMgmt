# G-code upload and analysis

TASK-042 introduced immutable local uploads. TASK-043 adds a bounded generic
parse summary. TASK-044 estimates filament weight, TASK-045 estimates print
time without claiming firmware-level precision, and TASK-046 detects material
from bounded evidence without turning detection into inventory recommendation.

## API

`POST /api/gcode/uploads` accepts one `multipart/form-data` field named `file`.
Only filenames ending in `.gcode` (case-insensitive) are accepted. MIME type is
not used as the authority because slicers and browsers commonly send generic
values.

Successful uploads return HTTP 201 with metadata only:

```json
{
  "upload_id": "93e88bde-fcb5-4929-b4a2-50c3d9f201cc",
  "filename": "Benchy.gcode",
  "size_bytes": 1234567,
  "created_at": "2026-09-01T10:00:00Z",
  "status": "UPLOADED"
}
```

`GET /api/gcode/uploads/{upload_id}` resolves a UUID and returns the same
metadata without returning file contents.

`POST /api/gcode/uploads/{upload_id}/parse` explicitly parses the immutable
upload and returns a small summary. FastAPI runs the synchronous local parser
in a threadpool so file I/O and parsing do not block the async event loop.

`POST /api/gcode/uploads/{upload_id}/weight` accepts one optional configuration
for each detected tool. A configuration may select a real `material_id` and may
provide an explicit `filament_diameter_mm`. The endpoint returns per-tool mass,
input provenance, a complete total only when every tool is calculable, and a
known subtotal for partial results.

`POST /api/gcode/uploads/{upload_id}/time` returns a cached, versioned time
analysis. It prefers an explicit slicer estimate and otherwise returns a
streaming command-kinematics heuristic.

`POST /api/gcode/uploads/{upload_id}/material-detection` returns a fresh,
per-tool material detection from the existing parse summary and the current
Material catalog. It is idempotent and creates no persistent record.

## Limits and storage

The per-file limit and the total storage quota are separate controls. The
backend defaults to a 100 MiB per-file limit and reads each `UploadFile` in
1 MiB chunks. `GCODE_MAX_UPLOAD_BYTES` can override the server limit with a
positive byte count. The optional frontend preflight limit uses the same
default and can be matched at build time with `VITE_GCODE_MAX_UPLOAD_BYTES`;
the backend remains authoritative.

The managed storage area defaults to a 2 GiB total quota. Usage is calculated
from filesystem metadata (`lstat` sizes), without opening G-code content. Raw
uploads, metadata, parse/time caches and temporary files count toward the
quota. Unexpected regular files directly inside the configured storage root
also count because they consume the same capacity, but cleanup never deletes
them blindly. Database, logs, generated manuals and files outside this root do
not count.

Lifecycle configuration uses environment variables:

| Variable | Default | Rule |
| --- | ---: | --- |
| `GCODE_MAX_UPLOAD_BYTES` | 100 MiB | Positive bytes; maximum for one file. |
| `GCODE_UPLOAD_MAX_TOTAL_BYTES` | 2 GiB | Positive bytes; total storage quota. |
| `GCODE_UPLOAD_RETENTION_DAYS` | 30 | Zero or greater; age from metadata `created_at`. |
| `GCODE_UPLOAD_RETENTION_ENABLED` | `true` | Explicitly enables/disables expiry. |
| `GCODE_UPLOAD_TEMP_STALE_SECONDS` | 3600 | Positive seconds before a known temp is stale. |
| `GCODE_UPLOAD_CLEANUP_ENABLED` | `true` | Enables automatic cleanup before uploads. |

Boolean values accept `true`/`false`, `1`/`0`, `yes`/`no`, and `on`/`off`
case-insensitively. Invalid values fail configuration loading. Retention day
zero means immediate eligibility at the deterministic `created_at <= cutoff`
boundary; use `GCODE_UPLOAD_RETENTION_ENABLED=false` to disable expiry without
ambiguity. There is no implicit negative or zero value for unlimited quota.

Files live under `data/uploads/gcode/` by default. An administrator may set
`GCODE_UPLOAD_DIRECTORY` to another controlled directory. Browser-provided
filenames are metadata only. Physical names are generated UUIDs:

```text
data/uploads/gcode/
  <upload_id>.gcode
  <upload_id>.json
  <upload_id>.parse.json
  <upload_id>.time.json
```

Data is first written as `<upload_id>.uploading`, size-checked while streaming,
and atomically renamed only after the complete upload arrives. Metadata uses the
same sidecar strategy. Empty, oversized, interrupted, or failed uploads are
cleaned up. Upload data is ignored by Git.

Before accepting a new upload, the service runs cleanup when
`GCODE_UPLOAD_CLEANUP_ENABLED=true`, recalculates current usage, and then checks
the declared size when available. Every streamed chunk is checked against both
the per-file limit and current total usage; the small metadata sidecar is also
checked before finalization. A failed size, quota, I/O, validation, or client
upload leaves no committed unit or partial temp under normal filesystem
operation. Real filesystem `ENOSPC`/quota errors and configured quota exhaustion
return HTTP 507 with a stable contract:

```json
{
  "detail": {
    "code": "gcode_storage_quota_exceeded",
    "message": "G-code storage has reached its configured limit."
  }
}
```

Parse and time caches also respect the total quota. Because they are derived
data, an analysis still returns its result when there is no capacity for a new
cache sidecar; the cache and its temporary file are simply not created.

Automatic cleanup removes expired units, safe orphans and stale known temps. It
never evicts a valid recent upload merely to admit a new one. If valid recent
data still fills the quota, the new upload is rejected. An already over-quota
directory is treated the same way: only policy-eligible data is removed.

Expiry uses the canonical `created_at` in `<upload_id>.json`; cache mtime and
filesystem access time never extend retention. A complete expired unit is
deleted in cache/temp, metadata, then raw-file order. A failed stage is reported
and leaves the remaining valid portion recoverable or identifiable on the next
idempotent run. Metadata cannot supply deletion paths: every target is rebuilt
from a validated UUID and a known suffix directly under the storage root.

Cleanup recognizes only the suffixes shown above and their real temporary forms:
`<upload_id>.uploading`, `<upload_id>.json.uploading`,
`<upload_id>.parse.json.uploading`, and `<upload_id>.time.json.uploading`.
Recent temps are preserved. Known stale temps and UUID-named raw, metadata or
cache orphans are eligible; unknown names and directories are retained with a
warning. Symlinks are never followed. A recognized unexpected symlink may be
unlinked inside the root, while its external target remains untouched.

Upload, parse and time-analysis operations register the UUID as active before
resolving or reading it. Cleanup and activity registration share process-local
locking, so cleanup either finishes before an analysis starts or skips that
unit for the full operation. Nested parse calls are reference-counted. No
distributed lock, scheduler, queue, or background loop is used.

Cleanup runs automatically before a new upload only. It does not run at app
startup. Administrators can run the same service manually from `backend/`, and
can later schedule this command with cron or a systemd timer:

```bash
python -m app.scripts.cleanup_gcode_uploads --dry-run
python -m app.scripts.cleanup_gcode_uploads
```

Dry-run reports uploads scanned, expired units, orphan/temp counts, reclaimable
bytes, usage, quota and over-quota state without deleting anything. The manual
command remains available when automatic cleanup is disabled;
`GCODE_UPLOAD_RETENTION_ENABLED` still controls whether age-based expiry is in
scope. Errors produce individual output and a non-zero exit code, while other
safe units continue to be processed.

The UUID is the safe hand-off between analysis tasks. Code must call
`GCodeUploadService.resolve_upload(upload_id)` rather than accepting an
arbitrary filesystem path.

## Generic parser

`GenericGCodeParser` is independent of FastAPI. It can parse a `Path` or a
single-pass iterable of text lines. Paths are opened read-only in binary mode
and consumed one bounded line at a time; the complete file and `readlines()`
are never used. NUL bytes reject the input as binary, while invalid UTF-8 text
is replaced with an explicit warning.

The line parser normalizes command case, supports irregular/no whitespace,
signed decimal and scientific numeric parameters, `N123` line numbers,
trailing checksums, semicolon comments, and simple parenthesis comments.
Unknown standard or vendor commands remain in bounded command counts but are
not interpreted semantically.

Generic state handling recognizes:

- movement/extrusion: `G0`, `G1`, `G2`, `G3`;
- units: `G20` (inches) and `G21` (millimeters);
- XYZ positioning: `G90`, `G91`;
- logical coordinate reset: `G92`;
- extrusion positioning: `M82`, `M83`;
- temperatures: `M104`, `M109`, `M140`, `M190` using `S`/`R` targets;
- basic volumetric configuration: `M200 D...`;
- any non-negative tool command `T0`, `T1`, and so on.

Linear extrusion under `G20` is normalized to millimeters. The final unit and
mixed-unit warning remain in the summary; axis coordinates are not retained.

## Extrusion semantics

Each tool owns its logical E position, retraction debt, linear total,
volumetric total, and volumetric-mode flag. In absolute and relative extrusion
modes, negative E movement adds retraction debt. Later positive E first repays
that debt; only the remainder counts as new commanded extrusion. `G92 E...`
changes the logical coordinate without adding physical movement. Switching
tools preserves every tool's state.

`extrusion_length_mm` is commanded filament length, not mass. `M200 D>0`
switches the selected tool to volumetric E values and records
`extrusion_volume_mm3`; `M200 D0` switches it back. Linear millimeters and
cubic millimeters are never added together. Mixed use produces a warning.

## Bounded summary and metadata

The summary contains counters, bounded command counts, final parser modes,
per-tool extrusion metrics, separate linear/volumetric totals, deduplicated
temperature targets, small key/value metadata, and deduplicated warnings. It
does not contain commands, coordinates, arbitrary comments, or source lines.

Comment metadata accepts `key = value` and `key: value`. Keys are normalized to
lowercase and duplicate keys use the last value. Limits are centralized at 64
keys, 64 characters per key, and 256 characters per value. Temperature,
command, and tool collections are bounded too. Truncation produces a warning.

Known `thumbnail ... begin/end`, preview, and image blocks are excluded before
metadata collection, so base64 previews cannot inflate the parse sidecar.

## Versioned cache

`parser_version` is currently `1`. The first parse writes
`<upload_id>.parse.json.uploading`, flushes it, and atomically renames it to
`<upload_id>.parse.json`. A matching version, UUID, filename, and source size
allows subsequent calls to reuse the cache. Invalid, oversized, mismatched, or
older-version caches cause a reparse. Parse summaries are limited to 1 MiB when
read and uploads are never modified.

## Estimated filament weight

`GCodeWeightService` consumes `GCodeParseResult` through the versioned parse
service. It does not scan the immutable `.gcode` again. Weight calculations are
cheap and request-dependent, so they are not persisted.

For linear extrusion, the service calculates circular filament volume and then
mass:

```text
volume_mm3 = extrusion_length_mm × pi × (diameter_mm / 2)²
weight_g = volume_mm3 / 1000 × density_g_cm3
```

For volumetric extrusion, `extrusion_volume_mm3` already represents volume, so
diameter is not applied again:

```text
weight_g = extrusion_volume_mm3 / 1000 × density_g_cm3
```

Every tool is calculated independently. A tool may contain linear, volumetric,
or both domains; mixed metrics remain separate in the parse summary and their
physical volumes can be combined without mixing millimeters with cubic
millimeters. Material density selected by the user has priority over explicit
`filament_density` metadata. If no material is selected, bounded physical
metadata may supply density. Diameter uses an explicit request first, followed
by `filament_diameter_mm` or `filament_diameter` metadata. Sources are returned
as `material`, `request`, `gcode_metadata`, or `not_available`.

The backend never assumes 1.75 mm. The frontend visibly prefills 1.75 mm when
metadata has no diameter, and the user can edit it. A selected material with no
density remains unavailable rather than receiving an invented default.

`total_estimated_weight_g` is present only when all detected tools are
calculable. `known_estimated_weight_g` is the sum of calculable tools and is
explicitly presented as a partial value when `is_complete` is false. Zero means
a known zero extrusion result; `null` means the estimate cannot be calculated.
Decimal arithmetic uses a high-precision pi constant and API results are rounded
once to three decimal places.

## Estimated print time

`GCodeTimeService` treats its two sources as alternatives and never adds them
together. Source precedence is:

1. a valid, explicit slicer metadata estimate (`slicer_metadata`);
2. the known time from command kinematics (`command_kinematics`);
3. `null` when neither source provides any duration.

The metadata recognizer uses exact semantic keys rather than searching every
comment containing the word `time`. Supported keys are `total estimated time`,
`estimated printing time`, `estimated print time`, their `(normal mode)` and
`(default mode)` variants, `TIME`, `print_time`, and `print time`. Other
parenthesized `estimated printing time (...)`/`estimated print time (...)`
variants are accepted only as lower-priority, explicit mode estimates. Values
may be seconds (`5423`), unit durations (`1h 30m 23s`, `1h 30m`, `30m 23s`),
or clock-like durations (`01:30:23`, `30:23`). Negative, non-finite,
arbitrary, malformed, and unreasonably large values are ignored safely.

Total, normal, and default estimates outrank generic estimates; generic
estimates outrank numeric `TIME`; `print_time`/`print time` and other explicit
modes follow. Selection is deterministic. Conflicting valid values are never
summed and produce `multiple_slicer_time_estimates`.

The fallback makes one bounded, line-by-line pass over the immutable upload.
It retains only small numeric state: XYZ and per-tool E positions, current
units, positioning modes, active tool, feed rate, speed factor, and accumulated
seconds. It never calls whole-file `read()` or `readlines()` and does not build
an AST.

Kinematic handling includes:

- persistent `F` in units per minute, normalized internally to mm/min;
- `G20` inches and `G21` millimeters;
- absolute/relative XYZ through `G90`/`G91`;
- absolute/relative E through `M82`/`M83`;
- Euclidean XYZ distance for `G0`/`G1`;
- E-only retract/unretract distance, without adding E to synchronized XYZ+E;
- logical coordinate changes from `G92` with zero elapsed time;
- `G4 P...` milliseconds and `G4 S...` seconds;
- persistent positive `M220 S...` speed factors;
- common `G17`/XY `G2` and `G3` arcs using `I`/`J` or `R`.

Unsupported arc planes and malformed arcs use chord distance only with
`arc_duration_approximated`. A real movement before any valid feed rate is not
assigned an invented speed: it increments `unestimated_motion_count`, emits
`missing_feedrate`, and makes `kinematic_is_complete` false. Known motion and
dwell seconds remain available as a partial heuristic.

The fallback is deliberately not a firmware planner. Acceleration,
deceleration, junction speed/jerk, machine limits, and firmware-specific macros
or overhead are not fully modeled. `M109`/`M190` heating waits, user-controlled
`M0`/`M1`/`M25` pauses, and machine-specific tool-change overhead receive no
fabricated duration and produce deduplicated warnings. The UI prefixes the
kinematic source with `~` and shows its relevant limitations compactly. When a
slicer estimate is the selected source, secondary kinematic warnings are not
presented as defects in the primary estimate.

`time_estimator_version` is currently `1`. The first analysis writes a small
`<upload_id>.time.json.uploading` sidecar, flushes it, and atomically renames it
to `<upload_id>.time.json`. Cache reuse requires the estimator version, UUID,
filename, and source size to match the immutable upload. Invalid, oversized,
mismatched, or old-version caches are recalculated. The cache contains only the
typed result and upload identity—not raw G-code.

TASK-045 does not modify `PrintJob`, select a spool, perform
recommendation/scoring, or reintroduce Advisor.

## Material detection

`GCodeMaterialDetectionService` uses the following conservative precedence:

1. explicit slicer metadata (`slicer_metadata`);
2. temperature ranges from the current Material catalog
   (`temperature_heuristic`);
3. unknown (`null` material and `NONE` confidence).

The service consumes the cached `GCodeParseResult`; it does not open or scan
the raw G-code. Detection is intentionally not cached because it is cheap and
must immediately reflect catalog edits.

Explicit keys are `filament_type`, `material_type`, `filament_material`, and
`material`, including indexed forms such as `filament_type_0`. A comma- or
semicolon-separated list is mapped to tools only when the values match the
contiguous `T0..Tn` tool set exactly. Non-contiguous tools require indexed
keys. A single global label is accepted only for a single-tool summary.
`filament_settings_id` is secondary evidence: an exact catalog label remains
`HIGH`, while a safe, unique whole-token match inside a profile name is
`MEDIUM`.

Catalog matching trims and collapses whitespace and compares case
insensitively. It otherwise remains exact. Therefore `PLA+` is not collapsed
to `PLA`, and `PETG-CF`, `PA-CF`, or `ABS-GF` are not collapsed to their base
materials. An explicit unmatched label is preserved with `HIGH` confidence
and a null catalog ID; detection never creates a Material automatically.

When explicit metadata is absent, the service compares operational nozzle and
bed targets with `default_nozzle_temp_min/max` and
`default_bed_temp_min/max` from the database. It contains no second hardcoded
material-temperature table and adds no tolerance outside those literal ranges.
A unique match using both nozzle and bed may be returned as `MEDIUM`. A match
using only nozzle or bed remains `LOW`; multiple matches also remain `LOW`,
return no selected material, and expose at most three deterministically ordered
candidates. Materials lacking the required ranges cannot receive a strong
temperature match.

Global temperatures are usable for one actively extruding tool. They are not
assigned across multiple actively extruding tools because the current generic
summary does not associate temperatures with tools. Tools seen only during
setup, with zero extrusion, do not make `is_complete` false. Explicit metadata
always wins over contradictory temperatures; a range conflict is reported as
`temperature_metadata_mismatch` without changing the selected material.

Confidence values are categorical, not statistical percentages:

- `HIGH`: explicit and unambiguous slicer label;
- `MEDIUM`: unique two-temperature catalog match, or safe profile-token clue;
- `LOW`: partial or ambiguous temperature evidence with bounded candidates;
- `NONE`: insufficient evidence.

The frontend runs detection automatically after parsing. A `HIGH` result with
a resolved catalog ID may prefill the corresponding Estimated Weight material
selector only while it is still untouched and empty. `MEDIUM` and `LOW` never
auto-select, and a manual user selection is never overwritten.

TASK-046 creates no database schema, Material, PrintJob, or inventory changes.
It provides no spool selection, compatibility scoring, or recommendation.
Advisor and the former TASK-047 remain absent.
