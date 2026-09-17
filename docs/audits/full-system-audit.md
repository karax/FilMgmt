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

REL-01 clean-checkout validation completed on 2026-09-07. Commit `4370ec9`
contains the previously omitted runtime, migration, test, tooling and product
documentation files, and the clean checkout passed backend/frontend tests,
migrations, build, manual generation, first-use, Print lifecycle, G-code and QR
gates without the user database or local dependencies. Committed Chromium
smoke passed 8/8 after first-use data existed but failed against empty user data;
the self-contained smoke correction then passed 8/8 in a second clean clone.
REL-01 is complete; its correction and setup contract remain preserved in the
current release working tree. See
`docs/audits/rel-01-clean-checkout-validation.md`.

Wave 1 completed on 2026-09-12. OPS-01 added a non-root user-systemd deployment,
Caddy same-origin frontend/API serving, a private LAN/Tailscale trust boundary,
verified online SQLite backup and guarded restore tooling, explicit-revision
update/rollback procedures, health checks, and power-loss recovery. Production-
like routing and Chromium smoke passed against a temporary restored database.

After challenge review, the high-priority risks for the supported private
Raspberry Pi/LAN/Tailscale deployment are:

- silent create/edit Print Job failures because the form ignores mutation
  errors;
- public Internet exposure remains prohibited until authentication exists.

Authentication is P2 defense in depth for a single operator behind a controlled
LAN/Tailnet, P1 for an untrusted LAN/Tailnet or multi-user mode, and a P0
precondition before any public Internet exposure. Localization, document
language, contrast and browser-only catalog onboarding were reclassified to P2.

Assessment: ready for a single-operator trusted LAN/Tailnet deployment using the
documented production model; not ready for multi-user use, an untrusted
LAN/Tailnet, or public Internet exposure.

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
| REL-01 | P0 gate — RESOLVED (2026-09-07) | Delivery | Original untracked-file omission was remediated and the clean-checkout path validated. | Product gates and empty-data smoke reproduce from the release working tree. | S | High |
| SEC-01 | P3 in supported private mode; P0 exposure gate | Security | No authentication/authorization protects archive, permanent delete, catalog mutation or 100 MiB upload; Swagger is always enabled. | Trusted LAN/Tailnet access remains the supported boundary; public, untrusted or multi-user deployment requires promotion and remediation first. | L | High |
| FUN-01 | P1 — RESOLVED (2026-09-09) | Core flow | PrintJobForm now consumes submitError and maps localized form/field errors, including nested spool rows. | Create/Edit preserve input, focus errors, prevent duplicate submits and support retry; conflict refresh retains the form. | S | High |
| I18N-01 | P1 — RESOLVED (2026-09-13) | i18n | Core Spool/Print and shared-shell copy now uses equivalent pt-BR/English resources; bounded statuses are localized. | Both supported languages render coherent core routes without fallback leakage in the tested matrix. | M | High |
| A11Y-01 | P1 — RESOLVED (2026-09-13) | Accessibility | The HTML language now initializes from and follows the validated selected locale. | Assistive technology receives `pt-BR` or `en` consistently with visible copy. | S | High |
| A11Y-02 | P1 | Accessibility | Light accent text is 2.74–3.00:1 and appears at 10–14 px. | Normal text fails WCAG AA; some focus indicators are also weak. | M | High |
| STO-01 | P1 — RESOLVED (2026-09-09) | Reliability | G-code storage now has configurable 30-day retention, a 2 GiB total quota, safe unit/orphan/temp cleanup, pre-upload enforcement and a dry-run CLI. | Upload growth is bounded without evicting recent or active analyses; quota/disk-full failures return structured HTTP 507 feedback. | M | High |
| OPS-01 | P1 — RESOLVED (2026-09-12) | Operations | Non-root systemd services, Caddy production serving, private access profiles, health, verified backup/restore, update/rollback and recovery tooling/runbook are implemented. | A private Pi can start at boot and be diagnosed, backed up, restored, updated and recovered without remembered development commands. | M | High |
| UX-01 | P1 | Onboarding | Catalog management is API-only; New Spool disables saving when catalogs are empty. | Clean installation cannot complete its primary UI flow without CLI/API knowledge. | L | High |
| DOC-01 | P1 — CONSOLIDATED/RESOLVED WITH OPS-01 (2026-09-12) | Documentation | Runtime documentation and the canonical production runbook now match the supported topology and commands. | Operators have one tested operations source linked from README. | M | High |
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
| TEST-02 | P2 | E2E | Smoke now covers the bilingual core-route matrix, persistence and translated mobile overflow, but not primary mutations, real upload or keyboard dialogs. | Important interaction regressions can still pass browser gates. | M | High |
| ARCH-01 | P2 | Maintainability | GCodeUploadPage (681 lines), parser (657), SpoolForm (489) and compressed one-line Print modules concentrate concerns. | Review/localization/change cost is unnecessarily high. | L | High |
| OBS-01 | P3 | Observability | No structured app logging, request IDs, metrics or disk/database health signal. | Field failures are difficult to diagnose. | M | High |
| DEP-01 | P3 | Reproducibility | Core Python dependencies use broad ranges rather than a lock/constraints file. | Fresh environments can receive materially different versions. | S | High |
| UX-04 | P3 | G-code | Analysis state is page-local; refresh loses upload ID while files remain. | Analysis cannot resume although storage accumulates. | M | High |

## Top 10 Recommended Improvements

1. Commit the validated README, self-contained smoke and audit closure; change REL-01 from
   conditionally ready to PASS.
2. Preserve the trusted LAN/Tailnet boundary; promote authentication only before
   public/untrusted exposure or use by multiple untrusted users.
3. Surface Print Job mutation errors with 409/422/network regression tests.
4. I18N-01/A11Y-01 completed: pt-BR/English resources, formatter behavior and the HTML language attribute are synchronized.
5. STO-01 completed: upload retention, total quota, cleanup and storage reporting are implemented.
6. Provide catalog management or an explicit first-run onboarding flow.
7. Fix light-theme contrast and modal/form-error accessibility.
8. OPS-01 completed: production/HTTPS/backup/restore guidance and tooling are published.
9. OPS-01 completed: README links the tested canonical operations runbook.
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

FUN-01 was resolved on 2026-09-09. PrintJobForm previously declared submitError
but omitted it from destructuring/rendering. Create/Edit now present persistent
pt-BR/en errors for 422 (including nested multi-spool paths), 400, 404, 409,
network failures, 5xx and unexpected responses. Unknown validation stays at
form level; mapped fields have aria-invalid/aria-describedby and receive focus.
Submitted row indexes map to stable row keys; corrections clear individual
errors. Values and estimated costs survive failure, including failed availability
refetches. Success keeps the existing /prints redirect and invalidations.
Save-only backend errors now expose stable codes and the affected spool ID;
IN_USE/EMPTY remain valid for planning, with availability restrictions enforced
at Start. PrintSpoolLock, Start/Finish behavior and schema are unchanged.
Evidence: 39 new page integration tests; 28 existing targeted Print tests;
11 targeted backend API tests; full frontend 313/313 and backend 448/448;
typecheck, build, compileall and alembic check passed. Chromium doctor was
healthy; Create and Edit failure/correction/retry passed at 390x844 with no
horizontal overflow. Screenshots are generated under frontend/test-results/e2e
by frontend/e2e/print-save-errors.spec.ts.

FAILED/CANCELLED should either gain supported transitions
with explicit lock/weight semantics or be removed until they do.

## Visual Design

The visual system is coherent: restrained surfaces, consistent cards, clear
badges, useful density and a strong industrial identity. Dark mode is mature.

The earlier screenshots recorded mixed-language Spool and Print controls. The
underlying interface labels, statuses and validation have now been localized;
the Portuguese guide wording was aligned without recapturing otherwise accurate
screenshots.

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

- introduce a darker light-theme accent-text token;
- use a modal primitive with focus trap, initial focus, inert background,
  Escape and restoration;
- connect field errors with aria-describedby/aria-errormessage and announce
  submit failures;
- continue broad accessibility review of names and descriptions beyond the
  i18n-specific labels localized by I18N-01;
- add automated keyboard/accessibility checks.

## UX Writing / i18n

i18next now covers the shared shell, Inventory, Spool, Print Tracker, QR,
G-code and Settings surfaces in pt-BR and English. Locale resources have runtime
recursive key-parity coverage, known API errors are mapped to localized copy,
and display formatting follows the selected locale while stored currency codes
remain authoritative. Entity/catalog data, FIL codes and raw G-code metadata
remain intentionally untranslated.

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
bounded reads/collections, no raw-content response, cleanup on failed upload,
retention and a total storage quota. STO-01 was resolved on 2026-09-09 with
logical-unit cleanup, orphan/stale-temp handling, process-local active-operation
protection, quota-aware derived caches, a dry-run CLI and structured HTTP 507/UI
feedback.

The app otherwise assumes a fully trusted network. CORS is not access control,
and the same-origin proxy exposes the whole API. Authentication, request limits
and HTTPS are prerequisites for broader exposure. Add configurable
docs exposure, trusted hosts, security headers, maximum concurrent analyses and
graceful disk-full behavior.

## Performance

At present volume (3 active Spools, 6 Print Jobs, 149 Materials), behavior is
adequate and G-code summaries are bounded. Upload growth now has retention and a
total quota; collections still return/render all rows and analysis concurrency
is unbounded.

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

README documents development and links the canonical production runbook.
`docs/operations/production-runbook.md` covers first-run catalogs, the production
topology/environment, private HTTPS/Tailnet camera access, the public-ingress
prohibition, database and optional upload backup policy, guarded restore,
migration-aware rollback, capacity checks, and power-loss recovery.

## Debt Summary

Architectural debt:

- oversized workflow/form modules and no common dialog/form primitive;
- unpaginated contracts and direct filesystem lifecycle;
- no centralized settings or authentication boundary;
- mixed formatting/style generations.

UX debt:

- API-only catalog onboarding;
- placeholder Analytics and missing 404;
- mobile header/table behavior;
- silent Print errors and no resumable G-code history.

Accessibility debt:

- insufficient accent contrast, modal focus defects, unassociated errors and no
  automated accessibility gate.

## Product / Technical Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Required untracked work omitted/lost | High | Critical | Track files; validate from fresh clone/git archive |
| Unauthorized network mutation | Medium–High | High | Auth, authorization, trusted exposure and HTTPS |
| Upload directory fills disk | Low after STO-01 | High | Configurable TTL/quota, safe pre-upload cleanup, dry-run CLI and structured disk-full handling implemented 2026-09-09 |
| Print save fails silently | Medium | High | Render mapped errors and preserve/focus state |
| Operator follows obsolete startup guidance | Low after OPS-01 | Medium–High | README links the tested production runbook and separates development mode |
| SQLite lock contention | Medium | Medium | WAL/busy policy, tests and deployment limits |
| Concurrent cache writers conflict | Low–Medium | Medium | Per-upload lock/single-flight or unique temp files |
| Assistive-technology barriers | High for affected users | Medium–High | Language, contrast, focus and error fixes |
| Location migration loses data | Low per upgrade | High | Backup, release note and restore test |
| Large datasets degrade all lists | Medium over time | Medium | Pagination and load tests |

## Final Assessment

The product has a stronger correctness core than its surface polish suggests.
Backend domain behavior and G-code parsing are carefully designed and tested;
the visual system and manual are coherent.

Wave 1 is complete: release reproducibility, Print save error handling, bounded
upload storage, and private-Pi production operations are implemented and
validated. The application now suits a trusted single-operator LAN/Tailnet
deployment. Authentication remains mandatory before public or untrusted
exposure; catalog onboarding, localization/accessibility, and pagination remain
later-wave work.
