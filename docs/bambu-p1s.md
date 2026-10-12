# Bambu Lab P1S local collector and print metadata (Waves 1–3)

## Scope

The backend can passively observe one Bambu Lab P1S over its local MQTT
interface. It connects to the configured printer, subscribes only to
`device/{serial}/report`, parses report JSON, keeps an in-memory normalized
state assembled from partial updates, persists printer-observed PrintJobs, and
enriches them from the printer's read-only implicit FTPS interface.
It exposes the current diagnostic state and persistent history at:

```text
GET /api/integrations/bambu/status
GET /api/prints
GET /api/prints/{id}
GET /api/prints/{id}/thumbnail
POST /api/prints/{id}/enrichment
```

The integration is deliberately read-only. It does **not** publish MQTT
messages, request `pushall`, start/pause/cancel prints, control motion or
temperatures, change AMS settings, associate AMS trays with inventory spools,
modify stock, upload/delete/rename FTPS files, or retain downloaded `.3mf`
archives. Current diagnostic state is rebuilt from reports after every
application restart; print history and normalized sliced metadata remain in
SQLite, while derived thumbnails use deterministic application storage.

The integration uses the printer's local interface rather than Bambu cloud or
community middleware. Bambu firmware may change field names, state strings, or
LAN access behavior; those changes should be isolated to the protocol adapter
under `backend/app/integrations/bambu/`.

## Configuration

Configuration follows the backend's existing environment-variable convention.
All three identity/credential values must be present before the collector starts:

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `BAMBU_HOST` | yes | none | P1S LAN IPv4 address or resolvable local hostname. |
| `BAMBU_SERIAL` | yes | none | Printer serial number used in the MQTT report topic. |
| `BAMBU_ACCESS_CODE` | yes | none | LAN/developer access code; treat as a secret. |
| `BAMBU_PORT` | no | `8883` | MQTT TCP port. |
| `BAMBU_FTPS_PORT` | no | `990` | Implicit-TLS FTPS port used only for read-only enrichment. |
| `BAMBU_MQTT_TLS` | no | `true` | Enable MQTT over TLS. Accepts `true`/`false`, `1`/`0`, `yes`/`no`, or `on`/`off`. |
| `BAMBU_DEBUG_PAYLOADS` | no | `false` | Emit bounded, de-duplicated DEBUG records containing only normalized known fields for fixture development. |
| `PRINT_JOB_MEDIA_DIRECTORY` | no | `data/print-jobs` | Internal directory for derived thumbnails. |

Blank or missing required values leave the integration disabled while the rest
of the application continues normally. Invalid port or boolean values are shown
as a safe diagnostic configuration error; their raw value is not logged.

For production, copy `deploy/env/production.env.example` to the existing
`~/.config/filament-command-center/env` file, uncomment the Bambu entries, fill
the real values, and keep that file mode `0600`. Never commit the installed file.

For local development, use an ignored environment file rather than putting the
access code in a command or shell history:

```bash
cd /path/to/FilMgmt
cp deploy/env/production.env.example .env
chmod 600 .env
# Edit .env and uncomment/fill BAMBU_HOST, BAMBU_SERIAL and BAMBU_ACCESS_CODE.
set -a
. ./.env
set +a
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Architecture and data model

```text
P1S report topic
  -> BambuMqttClient (TLS/authentication/subscription/reconnect only)
  -> BambuReportParser (protocol JSON -> normalized delta)
  -> BambuStateStore (thread-safe deep merge)
  -> BambuPrinterState (current in-memory snapshot)
  -> BambuPrintLifecycleDetector (de-duplicated internal events)
  -> BambuPrintJobCollector
  -> fresh SQLAlchemy session per callback
  -> SQLite PrintJob / history API

PrintJob enrichment trigger
  -> one serialized background worker (never the MQTT callback)
  -> BambuFtpsClient (implicit TLS, protected passive data channel, read-only API)
  -> conservative 3MF resolver (EXACT / HIGH_CONFIDENCE / AMBIGUOUS / NOT_FOUND)
  -> defensive ZIP/XML parser and plate selection
  -> one SQLAlchemy transaction
  -> PrintJob metadata + PrintJobFilamentUsage rows + derived thumbnail
```

The MQTT adapter has no publish method. The parser ignores unknown JSON fields
and maps known raw `gcode_state` strings into `UNKNOWN`, `IDLE`, `PREPARING`,
`PRINTING`, `PAUSED`, `FINISHED`, `FAILED`, or `CANCELLED`, while retaining the
raw state for diagnosis. Reports are treated as deltas: absent scalar fields,
AMS units, and trays retain their previous value. AMS units and trays are
upserted by their `id`, preparing a stable state that a later wave can snapshot
at print start without linking slots to inventory spools.

The normalized state includes filename/name/task identifiers, progress, layers,
remaining time, selected tray, AMS unit humidity/temperature, tray material,
color, profile/setting identifiers, brand, RFID tag UID, tray UUID, remaining
percentage and nozzle temperature range when the printer reports them. Unknown
values stay `null`.

## Persistent PrintJobs

Wave 2 extends the existing `print_jobs` table rather than creating a parallel
print domain. Existing manually planned jobs keep their `PLANNED`, `PRINTING`,
and `SUCCESS` behavior and spool links. Printer-managed jobs have
`capture_mode=LIVE` or `RECOVERED`, no spool links, and use `PRINTING`, `PAUSED`,
`COMPLETED`, `CANCELLED`, `FAILED`, or `UNKNOWN_TERMINAL`. The last value is the
safe fallback when an active print returns to `IDLE` without an explicit success,
failure, or cancellation report. Terminal captured jobs receive
`reconciliation_status=PENDING`; ambiguous terminal jobs use `NEEDS_REVIEW`.
No Wave 2 path calls inventory, weight, spool-status, or cost services.

The stored printer fields are serial, task/subtask/project/profile IDs, print
name, G-code filename, observation timestamps, raw Bambu state, start/latest
progress and layers, total layers, last remaining-time estimate, observed
duration, capture mode, reconciliation status, and a JSON AMS snapshot. A live
start stores its observed transition time. A recovered mid-print job leaves
`started_at` null rather than inventing a physical start time.

Identity uses `printer_serial` plus the Bambu `task_id`/`subtask_id` pair when at
least one task identifier is present. Filenames and names are metadata, never
run identities, because the same file can be printed repeatedly. When task IDs
are absent, a partial unique SQLite index enforcing one active captured job per
printer provides in-flight de-duplication. Repeated progress or terminal reports
therefore update or ignore the same row. After restart, a matching unfinished
row is resumed. If a new strong task identity conflicts with a stale unfinished
row, the stale row becomes `UNKNOWN_TERMINAL`/`NEEDS_REVIEW` and the new run is
captured separately.

The AMS snapshot is a detached JSON value created once with the current tray,
AMS units, trays, external tray, normalized material/color/profile/brand/tag/
UUID/remaining fields, and capture timestamp. Later state-store merges never
mutate historical snapshots.

Paho callbacks do not reuse FastAPI request sessions. The collector owns no
long-lived SQLAlchemy session: each received report opens a session from the
application session factory, reconciles one transaction under a process lock,
commits, and closes it. The partial unique index is the final duplicate-active-
job guard. Writes occur for lifecycle transitions, progress-percent changes,
terminal capture, recovery, or newly learned metadata; unchanged MQTT packets
do not dirty a PrintJob row.

Lifecycle detection recognizes the common Bambu states `IDLE`, `PREPARE`,
`RUNNING`, `PAUSE`, `FINISH`, and `FAILED`, plus documented aliases. It emits
internal/logged events named `PRINT_STARTED`, `PRINT_PROGRESS`, `PRINT_PAUSED`,
`PRINT_RESUMED`, `PRINT_FINISHED`, and `PRINT_ABORTED_OR_FAILED`. An unchanged
state and progress value emits nothing. A transition directly from an active
state to `IDLE` is treated as aborted/failed because no successful terminal
state was observed.

## Wave 3 FTPS and 3MF enrichment

The FTPS client reuses `BAMBU_HOST` and `BAMBU_ACCESS_CODE`, authenticates as
`bblp`, negotiates TLS immediately on port 990, then enables a protected passive
data channel. Certificate verification is disabled only in this dedicated P1S
TLS context because the printer presents a self-signed certificate. Its public
surface contains listing, metadata inspection, and download only; there is no
upload, delete, rename, directory creation, or generic FTP API.

Enrichment runs in one background thread so blocking FTPS I/O cannot block the
FastAPI event loop or Paho MQTT callback. Every enrichment phase opens its own
short-lived SQLAlchemy session. FTPS failures are converted to bounded status
codes and retry at most twice with 30-second and 5-minute delays. They do not
roll back the already committed MQTT PrintJob. Startup does not scan all
historical rows; an operator may retry one retained job with:

```bash
curl --silent --show-error --request POST \
  http://127.0.0.1:8000/api/prints/PRINT_JOB_ID/enrichment
```

The resolver first considers an exact reported path/name, then exact or
normalized filename stems, and only uses modification time to choose between
same-name candidates when one candidate is within 24 hours of the observed
start and separated from the runner-up by at least 30 minutes. It never guesses
from time alone. Multiple plausible matches become `AMBIGUOUS`; no first-file
fallback exists.

The parser reads only known archive members directly and never extracts the ZIP.
It rejects absolute/traversal paths, excessive member counts and decompressed
sizes, DTD/entity declarations, malformed XML, and non-PNG thumbnails. Unknown
XML fields and missing optional members are tolerated. Plate selection uses an
explicit MQTT/filename hint when available, otherwise a unique sliced plate,
unique embedded G-code reference, or unique active `filament_sequence.json`
entry. If several plates remain plausible, the job is marked `AMBIGUOUS`; their
usage is never summed.

Normalized `PrintJobFilamentUsage` children preserve the sliced filament ID,
material, color, estimated grams/metres, tray-info index, object/support flags,
nozzle diameter, group and plate. They deliberately have no `spool_id` and no
inventory relationship. Re-enrichment replaces the child set in one transaction
and therefore remains idempotent. `duration_seconds` remains observed duration;
`slicer_estimated_duration_seconds` is the separate slicer prediction.

Thumbnails are content-addressed PNG files under
`data/print-jobs/<job-id>/thumbnail-<digest>.png` (or the configured media
directory), written atomically. The database/API exposes only the controlled
thumbnail route, never a local path. Temporary `.3mf` downloads are deleted
after parsing and the source archive is not mirrored.

Observed on the real P1S used for Wave 3: `MLSD` was unavailable, while `NLST`,
`SIZE`, `MDTM`, protected passive `RETR`, and implicit TLS on port 990 worked.
A recent `/cache/*.3mf` contained 82 archive members and 14 plate previews. Its
`slice_info.config` identified plate 7, and only `Metadata/plate_7.gcode` was
present. `model_settings.config` named that plate and pointed to
`Metadata/plate_7.png`; `filament_sequence.json` also selected plate 7. The
sanitized metadata reported one PETG filament (`#FFFFFF`, 230.51 g, 75.46 m,
tray-info `GFG99`, 0.40 mm nozzle) and a 22,557-second prediction. These values
back the repository fixture; no printer credential, model geometry, embedded
G-code, serial, or personal filename is stored in it.

## Protocol assumptions

- MQTT uses protocol 3.1.1, username `bblp`, the configured access code as its
  password, and the exact `device/{serial}/report` topic at QoS 0.
- Local reports use a top-level `print` object and may contain only the fields
  that changed. `mc_remaining_time` is interpreted as minutes, matching the
  observed P1-series local MQTT payload convention.
- `gcode_state` commonly uses `IDLE`, `PREPARE`, `RUNNING`, `PAUSE`, `FINISH`,
  and `FAILED`. Unrecognized values remain available as `raw_state` and map to
  normalized `UNKNOWN` rather than failing the report.
- AMS unit/tray `id` values are treated as opaque strings. Colors, profile IDs,
  tag UIDs, and UUIDs are preserved as reported and are not interpreted as local
  inventory identities.
- The collector intentionally does not send `pushall`; initial state can remain
  incomplete until the printer naturally publishes the corresponding deltas.
- Lifecycle timestamps are observation times. If the collector starts while a
  print is already running, its first `RUNNING` report creates a `RECOVERED` job
  with a null `started_at` even though the physical print began earlier.

## Safe fixture capture

Normal operation never stores or logs raw MQTT payloads. For short development
sessions only, set `BAMBU_DEBUG_PAYLOADS=true` and enable DEBUG logging. The
service logs at most 200 unique normalized patches per process and omits unknown
payload properties, MQTT credentials, host configuration, and access codes.
Exact duplicate normalized patches are suppressed. Copy only the relevant
sanitized JSON value into a test fixture, then disable the flag. Do not redirect
an unrestricted long-running DEBUG log into the repository.

## TLS and credential security

The P1S normally presents a self-signed certificate on port 8883. With
`BAMBU_MQTT_TLS=true`, the collector creates one dedicated TLS client context,
requires TLS 1.2 or newer, and disables certificate/hostname verification only
inside that P1S MQTT context. TLS is not disabled globally and other application
traffic is unaffected. This encrypts the local connection but cannot prove that
the endpoint is the intended printer, so keep the printer and application on a
trusted, access-controlled LAN. `BAMBU_MQTT_TLS=false` exists only for firmware
or environments that expose plain MQTT.

The access code is sent only to the configured MQTT client as its password with
username `bblp`. It is excluded from setting representations, logs, exceptions,
and the diagnostic API. The backend does not send it to the frontend.

## Test with a real P1S

1. On the P1S, confirm it is connected to the same trusted LAN as the backend
   host and note its displayed IP address, serial number, and LAN access code.
   Depending on firmware, local third-party access may require LAN Only Mode
   and/or Developer Mode in the printer's network settings. Enable only the
   local-access setting your installed firmware requires; do not reset Wi-Fi,
   unbind the printer, or factory-reset it for this collector.
2. Fill the five variables shown below in the ignored environment file. Leave
   port 8883 and TLS enabled unless the printer's actual LAN behavior is known
   to differ.

   ```dotenv
   BAMBU_HOST=192.168.1.123
   BAMBU_PORT=8883
   BAMBU_SERIAL=01Pxxxxxxxxxxxx
   BAMBU_ACCESS_CODE=replace-with-the-printer-lan-access-code
   BAMBU_MQTT_TLS=true
   ```

3. Install/start the existing backend:

   ```bash
   cd /path/to/FilMgmt/backend
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

4. Apply migrations, then in another terminal inspect the safe diagnostic and
   recent persistent jobs repeatedly:

   ```bash
   curl --silent --show-error http://127.0.0.1:8000/api/integrations/bambu/status
   curl --silent --show-error 'http://127.0.0.1:8000/api/prints?printer_serial=01Pxxxxxxxxxxxx'
   ```

   A successful connection has `"configured":true`, `"connected":true`,
   `"connection_state":"CONNECTED"`, the configured serial, and eventually a
   non-null `last_update_at`. Startup logs include the connection and subscription
   without the access code.
5. Start a small print normally from Bambu Studio or Bambu Handy. Do not start it
   through this application. Re-run both requests and record the exact raw
   `gcode_state`, task/subtask IDs, name/file, progress, layer, AMS payload, and
   how many terminal reports arrive. Confirm one row changes through
   `PRINTING` to `COMPLETED`, its AMS JSON remains unchanged after a tray change,
   and no spool weight/status changes.
6. To exercise reconnect behavior, briefly interrupt only the printer's network
   path, then restore it. The status should move through `DISCONNECTED` and back
   to `CONNECTED`; a successful reconnect resubscribes automatically with an
   exponential delay capped at 60 seconds.

Common failures:

- `configured:false`: one or more required variables are missing, or a safe
  `configuration_error` identifies an invalid port/TLS value.
- Repeated connection failures: check the printer IP, same-LAN routing, guest
  network/client isolation, port 8883 reachability, and the firmware's current
  LAN/developer access setting.
- Connection rejected: re-check the LAN/developer access code rather than a
  cloud binding PIN. The code is case-sensitive.
- Connected but no updates: verify `BAMBU_SERIAL` exactly; it determines the
  subscribed topic. Because Wave 1 is passive and sends no `pushall`, the state
  fills as the printer emits report deltas and may initially contain `null`s.

No automated test requires a real printer. Physical-printer validation remains
necessary to confirm the installed firmware's TLS behavior, exact emitted field
set, report cadence, and terminal-state delivery.
