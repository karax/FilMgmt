# Filament Command Center — Full System Audit

> Status: complete. Audited on 2026-09-03 against the current working tree.

| Pass | Scope | Status |
|---|---|---|
| 0 | Product map and feature inventory | Complete |
| 1–4B | UX, flows, visual/mobile, accessibility, writing/i18n | Complete |
| 5–11 | Architecture, data, security, performance, tests, documentation | Complete |
| 12 | Synthesis, priority review and deduplication | Complete |

## Executive Summary

Filament Command Center is a credible local-first beta with unusually strong
domain rules, automated tests, G-code safety boundaries, responsive foundations,
and end-user documentation. Inventory, Print Tracker, QR and G-code analysis are
real integrated modules.

The working tree is healthy when executed in place: 443 backend tests, 274
frontend tests, type checking, production build, Python compilation, Alembic
drift checking and eight Chromium smoke scenarios passed on 2026-09-03. The
default SQLite database also passed integrity and foreign-key checks.

The immediate release blocker is delivery integrity. Fifty-five required files
are untracked, including the G-code API imported by the tracked application,
the current Alembic head, QR/G-code frontend code, browser tooling, tests and
user documentation. A fresh checkout of HEAD is not equivalent to the working
application.

After that blocker, the main risks are:

- no authentication or authorization on network-reachable write, upload and
  permanent-delete endpoints;
- silent create/edit Print Job failures because the form ignores mutation
  errors;
- incomplete Portuguese localization in core Spool and Print flows;
- no upload retention, quota or public cleanup mechanism;
- accessibility defects in language metadata, light-theme contrast, form
  errors and modal focus behavior;
- no production deployment, HTTPS, backup or recovery path;
- onboarding that depends on catalog seeds/API operations unavailable in UI;
- an obsolete root README that contradicts runtime and the current manual.

Assessment: strong beta for a technically supervised, trusted local environment;
not ready for unattended operation, multi-user use, or exposure to an untrusted
LAN/Tailnet.

## Product Map

    Application shell
    ├── Desktop sidebar / mobile navigation drawer
    ├── Sticky header, language-aware page title and theme switcher
    └── Root / redirects to /inventory

    Dashboard (/dashboard)
    ├── stock totals and remaining filament
    ├── low / empty / needs-drying indicators
    ├── per-material summary
    └── attention list

    Inventory (/inventory)
    ├── debounced search with URL state
    ├── filters and removable active-filter chips
    ├── table / grid view with local preference
    ├── archived records and QR scanner entry
    └── create, view, edit, weight, archive and delete Spool flows

    Print Tracker (/prints)
    ├── planned / printing / finished sections
    ├── multi-Spool create/edit
    ├── live estimated cost grouped by currency
    └── start/finish with optional actual consumption

    QR
    ├── per-Spool SVG generation and download
    ├── mobile landing (/qr/spool/:code)
    └── local camera decoder + FIL code fallback (/scan)

    G-code (/gcode)
    ├── validated streaming upload
    ├── bounded parse summary
    ├── estimated weight and time
    └── heuristic Material detection

    Analytics (/analytics)
    └── placeholder only

    Settings (/settings)
    ├── English / Portuguese (Brazil)
    └── downloadable PDF manual

    API-only catalogs
    ├── Manufacturer CRUD
    └── Material CRUD

### Backend/API map

- /api/health: health check.
- /api/spools: list/search/filter, create, read, patch, legacy put, weight,
  archive and delete.
- /api/prints: list/filter, create, read, update, start and finish.
- /api/manufacturers and /api/materials: catalog CRUD without management UI.
- /api/gcode/uploads: upload/read metadata, parse, weight, time and material
  detection.
- Persistence: Manufacturer, Material, Spool, WeightHistory, PrintJob,
  PrintJobSpool and PrintSpoolLock. Location is removed; Spool uses store_name.

## Audit Method

Evidence came from current source, schemas, migrations, the real SQLite
database, automated tests, production build, router/OpenAPI inspection,
Playwright Chromium, current screenshots and documentation. Roadmap/session
text was not treated as proof when it differed from runtime.

Validation on 2026-09-03:

- backend: 443 passed in 44.95 s;
- frontend: 26 files / 274 tests passed;
- typecheck, build, compileall and alembic check passed;
- build: 608.36 kB and 477.55 kB JavaScript chunks before gzip;
- Chromium smoke: 8 passed, including 390x844 overflow checks;
- SQLite: integrity_check = ok and foreign_key_check empty;
- accent #00a6a6 contrast: 3.00:1 on white, 2.74:1 on canvas.

No in-app browser instance was available. The repository's documented system
Chromium/Playwright path was used; that executor limitation is not a product
defect.

## Strengths Worth Preserving

- Domain mutations are service-owned and generally atomic. Weight history,
  derived status, print locks, archived records and cost snapshots have explicit
  rules and regression coverage.
- Foreign keys are enabled for each SQLite connection; migrations have real
  upgrade/downgrade and drift tests.
- Decimal values protect persisted weight, density and money.
- G-code upload uses UUID paths, bounded streaming, size checks, cleanup and
  atomic renames. Parsing is bounded, single-pass and does not expose raw code.
- G-code results distinguish known, partial, unavailable and heuristic values.
- QR payloads are network-independent; decoding is local and camera failure
  preserves a manual fallback.
- Responsive foundations include semantic tables, status text, progress
  semantics, labels, skip navigation, focus styles and reduced motion.
- Multi-currency Print totals remain separate and partial totals are honest.
- Test depth and reproducible user-guide screenshots are excellent for the
  project's size.

## Master Findings

Effort: S (hours), M (roughly 1–3 days), L (cross-cutting/multi-day).

| ID | Priority | Area | Finding | Impact | Effort | Confidence |
|---|---|---|---|---|---|---|
| REL-01 | P0 | Delivery | 55 required files are untracked, including imported runtime modules and the migration head. | Fresh checkout is incomplete; cleanup can lose delivered work. | S | High |
| SEC-01 | P1 | Security | No authentication/authorization protects archive, permanent delete, catalog mutation or 100 MiB upload; Swagger is always enabled. | Any reachable client can read or mutate the installation. | L | High |
| FUN-01 | P1 | Core flow | PrintJobForm accepts submitError but never reads it. | 409/422/network save failures are silent. | S | High |
| I18N-01 | P1 | i18n | Core Spool/Print UI is hard-coded English while pt-BR is default; raw OPEN-like statuses leak. | Default UI is visibly mixed-language. | M | High |
| A11Y-01 | P1 | Accessibility | HTML is permanently lang=en; language changes do not update it. | Screen readers may pronounce Portuguese as English. | S | High |
| A11Y-02 | P1 | Accessibility | Light accent text is 2.74–3.00:1 and appears at 10–14 px. | Normal text fails WCAG AA; some focus indicators are also weak. | M | High |
| STO-01 | P1 | Reliability | Successful G-code files/caches have no TTL, total quota, cleanup job/endpoint or UI removal. | Uploads can fill disk; 38 related files already exist locally. | M | High |
| OPS-01 | P1 | Operations | Docs stop at Vite dev/Uvicorn reload; no production service, HTTPS, backup or restore path exists. | Unattended recovery is undefined; remote camera use commonly fails on HTTP. | M | High |
| UX-01 | P1 | Onboarding | Catalog management is API-only; New Spool disables saving when catalogs are empty. | Clean installation cannot complete its primary UI flow without CLI/API knowledge. | L | High |
| DOC-01 | P1 | Documentation | README documents removed APIs, wrong routes/defaults, false limitations and a nonexistent command. | Operators/contributors receive contradictory guidance. | M | High |
| A11Y-03 | P2 | Accessibility | Dialogs do not trap focus; Spool archive does not move/restore focus; Print dialogs do not restore trigger focus. | Keyboard users can reach obscured content or lose position. | M | High |
| A11Y-04 | P2 | Accessibility | Form errors are not programmatically associated with controls. | Assistive technology cannot reliably discover field errors. | M | High |
| IA-01 | P2 | IA | Analytics is a primary-nav peer but only renders “Workspace ready.” | A prominent dead end weakens trust. | S | High |
| UX-02 | P2 | Mobile | Theme select truncates header titles; table-first Inventory scrolls horizontally to Status. | Context/data is hidden at 390 px despite no document overflow. | M | High |
| UX-03 | P2 | Navigation | There is no catch-all/errorElement product 404. | Invalid/deep links fall into router-default behavior. | S | High |
| FUN-02 | P2 | Inventory | Loading count renders the localized word “Retry.” | Misleading live-region feedback appears during load. | S | High |
| FUN-03 | P2 | Lifecycle | FAILED/CANCELLED are modeled/rendered but no API/UI transition creates them. | Advertised domain states are unreachable. | M | High |
| API-01 | P2 | Deployment | CORS allows GET only although VITE_API_BASE_URL supports split origin and UI uses POST/PATCH/DELETE. | Split-origin UI can read but not mutate. | S | High |
| PERF-01 | P2 | Performance | Collection APIs are unpaginated; Print lists include all associations. | Response/render/memory cost has no growth ceiling. | M | High |
| PERF-02 | P2 | Frontend | All routes are eager; build emits 608 kB and 478 kB JS chunks. | Inventory downloads unrelated G-code/QR modules. | M | High |
| REL-02 | P2 | Backend | Upload performs synchronous open/write/flush/fsync in an async endpoint. | Slow storage can block the event loop. | M | High |
| REL-03 | P2 | Backend | Concurrent parse/time calls share a fixed cache temporary path without coordination. | Work is duplicated and one cache writer may fail. | M | Medium |
| DATA-01 | P2 | Data | API maxima/format rules are not all mirrored by DB checks. | Imports/future internal writers can create API-invalid rows. | S | High |
| REL-04 | P2 | Database | SQLite uses rollback journal with no explicit WAL/busy policy. | Concurrent network writes face greater lock contention. | S | Medium |
| TEST-01 | P2 | Quality | No CI, lint/format gate, coverage floor, dependency scan or accessibility gate. | Strong local tests are not enforced; defect classes remain unchecked. | M | High |
| TEST-02 | P2 | E2E | Smoke checks presence/overflow, not primary mutations, real upload, language switch or keyboard dialogs. | Integration regressions can pass browser gates. | M | High |
| ARCH-01 | P2 | Maintainability | GCodeUploadPage (681 lines), parser (657), SpoolForm (489) and compressed one-line Print modules concentrate concerns. | Review/localization/change cost is unnecessarily high. | L | High |
| OBS-01 | P3 | Observability | No structured app logging, request IDs, metrics or disk/database health signal. | Field failures are difficult to diagnose. | M | High |
| DEP-01 | P3 | Reproducibility | Core Python dependencies use broad ranges rather than a lock/constraints file. | Fresh environments can receive materially different versions. | S | High |
| UX-04 | P3 | G-code | Analysis state is page-local; refresh loses upload ID while files remain. | Analysis cannot resume although storage accumulates. | M | High |

## Top 10 Recommended Improvements

1. Track all intended files and prove a fresh checkout can migrate, build and
   test.
2. Define the trust boundary and add authentication/authorization before
   network exposure.
3. Surface Print Job mutation errors with 409/422/network regression tests.
4. Complete pt-BR and synchronize the HTML language attribute.
5. Add upload retention, total quotas, cleanup and disk-health reporting.
6. Provide catalog management or an explicit first-run onboarding flow.
7. Fix light-theme contrast and modal/form-error accessibility.
8. Publish production/HTTPS/backup/restore deployment guidance.
9. Rewrite README from current runtime and test documented commands.
10. Add pagination, route code splitting and enforced CI quality gates.

## UX & Information Architecture

Inventory as root is defensible and the working modules have distinct jobs.
Contextual QR access avoids main-menu overload. Search/filter URL state, active
chips, retries, empty states and public code-based links are strong.

Analytics is a misleading primary-nav dead end. Catalog management is the
inverse problem: essential for first use but invisible. Missing branded 404,
ephemeral G-code analysis and the loading-count defect are smaller continuity
breaks.

## Functional Flow Findings

Backend Spool and Print mutations are strongly protected: archive-before-delete,
print locks, atomic weight history, conflicts and partial finish semantics are
good.

The major flow bug is silent Print save failure. In PrintJobForm, submitError is
declared but omitted from destructuring/rendering. Client errors are also
hard-coded English. FAILED/CANCELLED should either gain supported transitions
with explicit lock/weight semantics or be removed until they do.

## Visual Design

The visual system is coherent: restrained surfaces, consistent cards, clear
badges, useful density and a strong industrial identity. Dark mode is mature.

Screenshots also prove mixed-language inconsistency. Spool details/creation and
Print creation combine Portuguese with “Edit Spool,” “Add Spool,” “Hours,”
“Cancel,” raw statuses and English validation. These are product defects, not
documentation defects.

## Responsive / Mobile

Shell, forms, uploader and scanner fit 390x844 without document overflow.
Newer QR/G-code touch targets are generally 44–48 px.

The header theme select visibly truncates titles such as “Nova Impress…”.
Table is the mobile Inventory default and requires horizontal scrolling to
reach Status. Prefer Grid below the mobile breakpoint or a purpose-built compact
list.

## Accessibility

Strengths: semantic tables, real controls, status text beyond color, progress
semantics, labels, skip link, visible focus and reduced motion.

Required:

- synchronize document lang;
- introduce a darker light-theme accent-text token;
- use a modal primitive with focus trap, initial focus, inert background,
  Escape and restoration;
- connect field errors with aria-describedby/aria-errormessage and announce
  submit failures;
- localize accessible names such as Color, Remaining and loading labels;
- add automated keyboard/accessibility checks.

## UX Writing / i18n

i18next covers newer QR/G-code and much of Print Tracker, but legacy Spool
surfaces bypass it. Hard-coded text appears in NewSpoolPage, EditSpoolPage,
SpoolDetailsPage, SpoolForm, PrintJobForm, ThemeToggle, SpoolProgressBar,
SpoolColorIndicator and PagePlaceholder.

Several required translation keys already exist. Wire them, add the missing
keys and enforce key parity. Replace late Object.assign locale extensions with
one typed structure per locale.

## Frontend Architecture

Query keys/invalidation, shared formatters and QR helpers are disciplined.
Debt is concentrated in oversized components, eager routes and inconsistent
generations of UI code.

Recommended boundaries:

- lazy route modules with Suspense/error states;
- G-code workflow controller plus separate panels;
- reusable FormField and accessible Dialog primitives;
- typed translation parity;
- domain API error adapters rather than string matching in components.

## Backend Architecture

The service/router split is clear and sync SQLAlchemy endpoints correctly use
normal def functions. G-code analysis is sent to a threadpool.

Upload destination I/O is the exception because it blocks inside async code.
Cache generation needs per-upload single-flight/locking. Reformat and split
PrintJobService before extending the lifecycle. Consolidate environment values
into one validated settings object covering database, uploads, CORS, docs and
trust/auth.

## Domain & Data Integrity

The current DB passed integrity/FK checks. Unique codes, link uniqueness, print
locks, timestamp order, positive weights and status checks are valuable.

Mirror long-lived API invariants at the DB layer or make API-only writing an
explicit contract and validate imports. Revisit whether purchase price 100 is a
real invariant; enforce it consistently if it is.

Location removal intentionally deletes catalog data and downgrade cannot
restore it. Require a pre-upgrade backup and explicit release note.

## Security & Reliability

G-code traversal and memory-amplification defenses are strong: UUID paths,
bounded reads/collections, no raw-content response and cleanup on failed upload.

The app otherwise assumes a fully trusted network. CORS is not access control,
and the same-origin proxy exposes the whole API. Authentication, request limits,
upload quotas and HTTPS are prerequisites for broader exposure. Add configurable
docs exposure, trusted hosts, security headers, maximum concurrent analyses and
graceful disk-full behavior.

## Performance

At present volume (3 active Spools, 6 Print Jobs, 149 Materials), behavior is
adequate and G-code summaries are bounded. Growth lacks ceilings: collections
return/render all rows, uploads persist forever and analysis concurrency is
unbounded.

Add pagination before inventory/history grows. Route-level splitting should
reduce initial load; measure rather than raising the 500 kB warning.

## Testing & Engineering Quality

The 717 unit/component/API tests and real Chromium smoke suite are a major
strength. Migrations, parser edges, multi-Spool conflicts, camera cleanup,
languages and partial totals receive careful coverage.

Missing enforcement/breadth:

- CI on a clean checkout;
- lint/format/static Python and coverage gates;
- dependency vulnerability automation;
- accessibility and focus-sequence tests;
- E2E primary mutations and real G-code upload;
- concurrent cache and print lifecycle tests.

## Documentation

The Portuguese manual, Print Tracker guide, QR format, G-code contract and
headless-browser guide are useful and evidence-rich.

README preserves an early product state and now contradicts routes, APIs,
features, API base behavior and browser installation. Rewrite it rather than
patching isolated sentences.

Operational docs still need first-run catalogs, production topology/environment,
HTTPS/Tailnet camera guidance, coordinated database/upload backup/restore,
destructive migration notes, retention/capacity planning and a clean-checkout
release checklist.

## Debt Summary

Architectural debt:

- oversized workflow/form modules and no common dialog/form primitive;
- unpaginated contracts and direct filesystem lifecycle;
- no centralized settings or authentication boundary;
- mixed formatting/style generations.

UX debt:

- mixed-language flows and API-only catalog onboarding;
- placeholder Analytics and missing 404;
- mobile header/table behavior;
- silent Print errors and no resumable G-code history.

Accessibility debt:

- incorrect language, insufficient accent contrast, modal focus defects,
  unassociated errors, hard-coded English accessible names and no automated
  gate.

## Product / Technical Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Required untracked work omitted/lost | High | Critical | Track files; validate from fresh clone/git archive |
| Unauthorized network mutation | Medium–High | High | Auth, authorization, trusted exposure and HTTPS |
| Upload directory fills disk | High over time | High | TTL, quota, cleanup and disk telemetry |
| Print save fails silently | Medium | High | Render mapped errors and preserve/focus state |
| Operator follows obsolete README | High | Medium–High | Rewrite and test documented commands |
| SQLite lock contention | Medium | Medium | WAL/busy policy, tests and deployment limits |
| Concurrent cache writers conflict | Low–Medium | Medium | Per-upload lock/single-flight or unique temp files |
| Assistive-technology barriers | High for affected users | Medium–High | Language, contrast, focus and error fixes |
| Location migration loses data | Low per upgrade | High | Backup, release note and restore test |
| Large datasets degrade all lists | Medium over time | Medium | Pagination and load tests |

## Final Assessment

The product has a stronger correctness core than its surface polish suggests.
Backend domain behavior and G-code parsing are carefully designed and tested;
the visual system and manual are coherent.

Release readiness is blocked by source-control incompleteness. Network
production readiness is blocked by the absent trust boundary, upload lifecycle
and runbook. User readiness is blocked chiefly by catalog onboarding, silent
Print save failures and incomplete localization/accessibility.

After Wave 1 of the backlog, the application should suit a trusted
single-operator deployment. Authentication, capacity controls, pagination and
production operations should precede multi-user or broadly reachable use.
