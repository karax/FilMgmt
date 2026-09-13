# REL-01 — Clean Checkout Validation

Date: 2026-09-07

## Scope

Validate that a new clone can install, migrate, test, build, generate its
manual, start, and exercise the supported first-use flows without borrowing
the source working tree's virtual environment, `node_modules`, database,
uploads, generated output, or untracked product files.

The committed revision and the uncommitted remediation are reported separately.

## Source Revision

- Branch: `refactor`
- Commit: `4370ec9bbcccbe7742e9f1761defbd0f7e9e2970`
- Commit subject: `4370ec9 Audit`
- Source working tree: dirty before validation. The required product-related
  differences were a setup README correction and, after reproducing the issue,
  a clean-data Chromium smoke correction. Audit notes were kept separate.

## Environment

- Architecture: `aarch64` / ARM64
- OS: Debian GNU/Linux 13
- Python: 3.13.5
- Node: 24.20.0
- npm: 11.19.0
- Chromium: 151.0.7922.173
- Playwright: 1.62.1

## Clean Checkout Method

A local `git clone --no-local` created `<validation-root>/clean-repo` on a
filesystem outside the source repository. Its initial `git status --short`
was empty and its revision matched the source `HEAD`.

The clone initially contained none of the following runtime/generated paths:
`.venv`, `node_modules`, `data/filament.db`, backups, uploads,
`frontend/dist`, test results, Playwright reports, or `.env`.

The first attempt used the executor's small `/tmp` tmpfs and both installers
encountered `ENOSPC`. That partial clone was deleted and a completely new
clone was created on the normal filesystem, which had sufficient space. This
was an executor storage limitation, not a project defect, and no partial
installation was reused.

After remediation, a second `git clone --no-local` created
`<remediated-validation-root>/clean-repo`. The exact working-tree diff for
`README.md` and `frontend/e2e/smoke.spec.ts` was applied mechanically;
hashes matched the source working tree. No product artifact was copied.

## Backend Installation

- Created a new virtual environment inside the clean clone.
- Installed production and development dependencies only from tracked
  `requirements.txt` and `requirements-dev.txt`.
- Installation passed on ARM64; `pip check` found no broken requirements.
- The manifests contain exact pins for core packages and bounded ranges for
  Alembic/SQLAlchemy. They are sufficient to install, but do not provide a
  fully frozen transitive Python lock.

## Frontend Installation

- `package-lock.json` exists at lockfile version 3.
- `npm ci` installed 151 packages from the tracked lockfile.
- npm reported zero vulnerabilities and no peer-dependency conflict.
- No prior `node_modules` or local link was used.

## Empty Database Migration

- A new SQLite file outside the clone was created only by
  `alembic upgrade head`.
- All migrations ran from base through `f2a8c7d190b4`.
- `alembic current`: `f2a8c7d190b4 (head)`.
- `alembic heads`: one head, `f2a8c7d190b4`.
- `alembic check`: no new upgrade operations detected.
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: zero rows.
- Canonical tables exist: manufacturers, materials, spools, weight_history,
  print_jobs, print_job_spools, and print_spool_locks.
- Removed Location storage is not present in the final schema.
- `print_jobs` does not revive the legacy root `spool_id`,
  `estimated_weight_g`, `actual_weight_g`, or cost columns.

## Seeds / Bootstrap

The documented commands populated 20 manufacturers and 149 materials and were
sufficient to create the first Spool. PLA included the implemented nozzle and
bed temperature defaults.

The current canonical material seed stores no density values. This does not
block Spool onboarding. G-code weight remains available when density is
provided by slicer metadata or another supported source.

## Test Results

- Backend: 443 passed in 42.62 seconds; one dependency deprecation warning.
- Frontend: 26 files / 274 tests passed in 189.93 seconds.
- Python compilation: PASS.
- TypeScript typecheck: PASS.
- The remediated smoke file also passed typecheck in the second clone.

## Build Results

- Clean production build: PASS.
- Vite transformed 2,228 modules.
- Output included the known 608.36 kB and 477.55 kB JavaScript chunks before
  gzip; the existing chunk-size warning is non-blocking.
- `frontend/dist` was generated inside the clean clone.

## Chromium Smoke

- `npm run browser:doctor`: PASS; Chromium, frontend, and backend found.
- Committed `HEAD` against a migrated/seeded but empty database: FAIL —
  6 passed, 1 skipped, 1 failed. The Inventory scenario required a table even
  when the product correctly rendered its empty state; the details scenario
  skipped when no Spool existed.
- Committed `HEAD` after the supported first Spool was created: 8 passed.
- Remediated working tree in the second clone, starting with no user Spool:
  8 passed. The smoke now accepts the intentional empty Inventory state and
  creates its own details fixture from the seeded catalogs when necessary.

The failure was therefore a test-data reproducibility defect, not a product
rendering defect or Chromium sandbox limitation.

## Manual PDF

- Tracked Markdown source and referenced assets were present.
- `npm run docs:pdf`: PASS from the clean clone.
- Generated PDF: 2,472,854 bytes, valid PDF, 53 A4 pages.
- `npm run docs:pdf:check`: PASS.
- A build rerun after generation copied a byte-identical PDF to
  `dist/docs/filament-command-center-user-guide.pdf`.
- Chromium verified the Settings download URL, MIME type, PDF signature, and
  suggested filename.
- The generated tracked PDF was restored to `HEAD` in the validation clone
  after evidence collection; generated validation output was not mixed with
  committed-artifact evidence.

## First-Use Functional Flow

- Catalog: 20 manufacturers and 149 materials available after documented
  bootstrap.
- Spool: created `FIL-0001`; visible through Inventory, detail API, and
  browser details route.
- Print: created PLANNED with a 25 g estimate and cost-capable spool data.
- Start: Print became PRINTING and Spool became IN_USE.
- Finish: Print became SUCCESS; 20 g consumption produced EUR 0.5000 cost,
  Spool weight became 980 g, and status recalculated to OPEN.
- Reuse: a second Print started and finished with the same Spool.
- G-code: a small fixture derived from tracked test literals passed upload,
  parse, HIGH-confidence PLA detection, 0.030 g weight estimate, and 120 s
  time estimate.
- QR: browser confirmed the canonical `fcc:spool:FIL-0001` SVG payload,
  QR landing, and manual FIL-code scanner fallback. No camera was required.

## Hidden Dependency Checks

- Required untracked files: none in committed `HEAD`.
- Personal absolute runtime paths: none.
- Hardcoded personal LAN/Tailscale addresses: none.
- Frontend runtime API model: relative `/api`; Vite proxy to the intentional
  local backend at `127.0.0.1:8000` passed.
- Missing generated/static assets: none; the manual PDF is tracked and is also
  reproducible.
- Secrets: no private key, credential-shaped token, API key, or assigned secret
  found in tracked text. Secret values would have been suppressed.
- The clean clone returned to an empty Git status after the regenerated tracked
  PDF was restored; ignored environments/build/reports introduced no required
  untracked product path.
- The real database, uploads, backups, and user history were not used or
  modified.

## Documentation Review

Committed `HEAD` is not sufficient as setup documentation. Its README names
removed Location behavior and stale features/routes, uses `npm install`,
references a nonexistent browser-install script, describes an absolute
localhost frontend API default, and advertises a Node version below the locked
jsdom engine requirement.

The uncommitted minimal README correction documents:

- Linux/POSIX assumptions;
- Python and tested Node 24.x/npm 11 versions;
- backend production/development dependency installation;
- empty database migration and both catalog seed commands;
- backend and frontend startup;
- reproducible `npm ci`;
- relative `/api` proxy behavior and application URL;
- the actual browser doctor command and current feature/routes.

Production service, HTTPS, backup, restore, upgrade, and rollback remain outside
REL-01 and belong to the later runbook task.

## Findings

1. Historical source omission: remediated by commit `4370ec9`; not active.
2. Setup README: corrected locally and validated, but uncommitted.
3. Chromium smoke hidden fixture dependency: corrected locally and validated
   from an empty second clone, but uncommitted.
4. Python transitive resolution is bounded but not fully locked; this remains
   the existing lower-priority DEP-01 risk, not a failure of this installation.
5. The initial `/tmp` `ENOSPC` was an external executor limitation and
   disappeared in a new clone on a filesystem with adequate capacity.

## Required Fixes

1. Commit the validated `README.md` setup correction.
2. Commit the self-contained `frontend/e2e/smoke.spec.ts` correction.
3. Track this closure report and the REL-01-only audit/backlog updates.

No application runtime code change is required.

## Validation Matrix

| Check | Result | Evidence |
|---|---|---|
| Clean clone | PASS | New `--no-local` clone; empty initial status; 306 tracked files |
| Backend install | PASS | Fresh venv; tracked requirements only; ARM64 |
| Frontend `npm ci` | PASS | 151 packages; lockfile v3; zero vulnerabilities |
| Alembic from empty DB | PASS | Base through single head `f2a8c7d190b4` |
| SQLite integrity | PASS | `ok`; zero FK violations |
| Backend tests | PASS | 443 passed |
| Frontend tests | PASS | 274 passed |
| Typecheck | PASS | Clean HEAD and remediated smoke |
| Build | PASS | 2,228 modules; clean `dist` |
| Chromium smoke | CONDITIONAL | HEAD needs a Spool for 8/8; uncommitted self-contained fix passes 8/8 from empty data |
| Manual PDF | PASS | Generated, checked, 53 pages, present byte-identically in build |
| Create Spool | PASS | `FIL-0001`, Inventory and Details |
| Create Print | PASS | PLANNED, 25 g estimate |
| Start/Finish | PASS | IN_USE then OPEN; second Print reused same Spool |
| G-code | PASS | Upload, parse, material, weight, time |
| QR | PASS | Render, landing, manual fallback |
| Hidden dependencies | PASS | No required local DB/env/modules/path/IP/secret |
| Setup documentation | CONDITIONAL | Corrected and clean-validated, but uncommitted |

## Final Status

**CONDITIONALLY READY**

The system is reproducible from the committed source once supported first-use
data exists, and all application/build/database/manual/functional gates pass.
However, committed `HEAD` still contains insufficient setup instructions and
a browser smoke suite that does not pass all eight scenarios from empty user
data. The exact uncommitted remediation passes in a second new clone.

REL-01 becomes **PASS** when the README, self-contained smoke correction, and
closure audit documents are committed. No external or untracked runtime state
is required.
