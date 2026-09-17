# Improvement Backlog

> Status: synthesized from the completed full-system audit on 2026-09-03.
> Priority: P0 release blocker, P1 high, P2 medium, P3 low.
> Challenge review: priorities and Wave 1 were revised on 2026-09-03 in
> `docs/audits/p0-p1-closure.md`.

## P0 — Critical

### REL-01 — Make the delivered source reproducible — RESOLVED (2026-09-07)

- Status: **COMPLETE** on 2026-09-07.
- Original issue: required files were untracked. Remediation: commit `4370ec9`
  added 107 individual paths; the earlier approximate count of 55 is not an
  active defect.
- Clean checkout passed fresh dependency installation, empty migration, 443
  backend tests, 274 frontend tests, compile, typecheck, build, PDF generation,
  first-use, Print reuse, G-code, QR and hidden-dependency gates. Committed
  Chromium smoke passed 8/8 after first use but failed against empty user data.
- A self-contained smoke correction passed 8/8 from empty data in a second new
  clone. The minimal README setup correction also passed the documented clean
  install path.
- The validated README, self-contained smoke correction, and audit record are
  preserved in the current release working tree. No application runtime
  remediation remains. See `docs/audits/rel-01-clean-checkout-validation.md`.

## P1 — High

### FUN-01 — Show Print Job save failures — RESOLVED (2026-09-09)

- Create/Edit consume submitError using the existing ApiError/detail infrastructure
  and a Print-specific normalizer; 422 nested paths map to stable spool row keys.
- Persistent pt-BR/en field/form feedback covers validation, 400/404/409, network,
  5xx and malformed responses. Unknown fields remain visible at form level.
- Input and live estimated costs survive failure/refetch; corrections clear field
  errors, focus moves to the first invalid field or alert, and loading blocks
  duplicate submits. Retry retains the existing success navigation/invalidations.
- Save error contracts provide codes/spool IDs. Conflict refresh is limited to
  spool queries; planning with IN_USE/EMPTY, Start/Finish and locks are unchanged.
- Acceptance passed: 39 new frontend integration tests, 28 existing targeted Print
  tests, 11 targeted backend API tests; full frontend 313/313, backend 448/448,
  typecheck, build, compileall and alembic check. Chromium doctor and two real-route
  Create/Edit failure/retry scenarios passed at 390x844, with screenshots and no
  horizontal overflow. No schema changes or migration.

### STO-01 — Add a G-code storage lifecycle — RESOLVED (2026-09-09)

- Configurable defaults: 30-day metadata-based retention, 2 GiB total quota,
  one-hour stale-temp age, automatic pre-upload cleanup and the existing 100 MiB
  per-file limit kept separate.
- Cleanup treats UUID-named raw, metadata, parse cache and time cache as a logical
  unit; removes safe orphans/stale known temps; ignores unknown entries; does not
  evict recent data; and never follows metadata paths or symlinks.
- Upload, parse and time operations use process-local active markers and shared
  filesystem-operation locks. Upload quota is checked after cleanup, while
  streaming and before atomic metadata finalization. Derived parse/time caches
  are skipped when they cannot fit, so analysis still succeeds without taking
  storage over quota. Partial files are removed.
- HTTP 507 exposes `gcode_storage_quota_exceeded`; `/gcode` shows persistent
  localized pt-BR/en feedback. Manual cleanup and `--dry-run` reuse the service.
- Acceptance passed: 50 focused backend storage/upload tests, 103 parser/time/
  weight/material regression tests, 36 focused G-code page tests, full backend
  479/479 and frontend 315/315, compileall, Alembic check, typecheck and build.
  Chromium doctor passed; interactive browser validation was unavailable because
  this session had no connected controllable browser. No schema change/migration.

### OPS-01 — Define supported production operations — RESOLVED (2026-09-12)

- Added non-root user services for loopback Uvicorn, Caddy static/proxy serving,
  and an optional verified daily-backup timer. The production Caddy route serves
  only `frontend/dist`, proxies `/api` first, preserves SPA deep links and the
  manual PDF, and leaves API 404 responses as JSON.
- Added a production environment example plus quick/deep health, SQLite online
  backup, manifest/checksum verification, guarded atomic restore, and explicit-
  revision update commands. Dirty trees stop updates; rollback never assumes
  Alembic downgrade is safe.
- `docs/operations/production-runbook.md` now covers setup, services, journald,
  LAN/Tailscale HTTPS/public-ingress boundaries, G-code policy, backup/restore,
  update/rollback, power loss, disk maintenance, and disaster recovery. The root
  README links to it.
- Acceptance passed: 9 targeted operations test groups, backend 488/488,
  frontend 315/315, compileall, Alembic drift check, TypeScript typecheck and
  production build. Systemd and Caddy syntax validation passed. A temporary
  restore drill preserved all current canonical record groups with
  `integrity_check=ok` and zero foreign-key violations. Production-like Caddy
  routing and Chromium smoke passed 8/8. No schema change or migration.

## P2 — Medium

### SEC-01 — Establish the application trust boundary

- Priority basis: P2 for a single operator behind a controlled LAN/Tailnet; P1
  for an untrusted LAN/Tailnet or multi-user mode; P0 exposure gate before
  public Internet ingress.
- For the supported private mode, document and enforce the network boundary and
  limit reachability. Tailscale membership is the current admission control.
- Before broader exposure, protect reads and mutations, use stronger
  authorization for catalog mutation/archive/delete/uploads, and control
  docs/OpenAPI exposure.
- Acceptance for authenticated mode: anonymous clients cannot access protected
  data or mutate state; authorization tests cover destructive/upload endpoints.

### I18N-01 / A11Y-01 — Complete language behavior — COMPLETE (2026-09-13)

- Shared-shell and core-route copy is present in both locale resources.
- Bounded Spool/Print statuses render localized labels while stored values remain stable.
- `document.documentElement.lang` follows validated initialization and language changes.
- Recursive key parity, formatter semantics, language persistence and a bilingual
  core-route/mobile browser matrix are covered.
- Acceptance passed: the tested pt-BR and English routes contain no unintended
  opposite-language copy and the DOM language matches the selected locale.

### A11Y-02 — Correct light-theme contrast

- Split decorative accent from an accessible accent-text/focus token.
- Reach at least 4.5:1 for normal text and 3:1 for non-text focus indicators.
- Recheck links, FIL codes, eyebrows, selected view text and small dashboard
  actions in light mode.
- Acceptance: measured pairs pass WCAG AA and visual snapshots are reviewed.

### UX-01 — Unblock clean-install catalog onboarding

- Add Manufacturer/Material management in Settings, or a first-run wizard that
  safely runs/validates seed data.
- Replace “Create first” dead-end messages with direct actions.
- Preserve referential-integrity warnings when editing/deleting catalog items.
- Acceptance: a browser-only user can go from an empty DB to the first Spool.

### A11Y-03 / A11Y-04 — Standardize accessible dialogs and forms

- Create one Dialog primitive with initial focus, focus containment, inert
  background, Escape, pending-state rules and trigger restoration.
- Create one FormField primitive that owns stable help/error IDs and
  aria-describedby/aria-errormessage.
- Migrate Spool and Print forms/dialogs and add keyboard tests.
- Acceptance: Tab/Shift+Tab never leave a modal; focus returns to its trigger;
  screen readers receive field and submit errors.

### IA-01 — Resolve Analytics navigation

- Hide Analytics until useful, label it explicitly as preview, or deliver a
  minimum useful dashboard.
- Acceptance: primary navigation contains no unqualified placeholder module.

### UX-02 / UX-03 — Improve mobile and route recovery

- Use a compact theme control/menu on narrow headers and preserve full page
  context accessibly.
- Default mobile Inventory to Grid or implement a compact list; retain Table as
  an explicit comparison mode.
- Add localized branded 404/errorElement with safe navigation home.
- Acceptance: 320/390 px screenshots show full title/context and primary Spool
  state without mandatory horizontal discovery.

### FUN-02 — Correct Inventory loading count

- Render a skeleton/ellipsis or suppress the count while it is unknown.
- Acceptance: loading never announces “Retry” as an inventory count.

### FUN-03 — Reconcile Print lifecycle states

- Either implement Cancel/Fail transitions with lock release and weight
  semantics, or remove unreachable statuses from active product contracts.
- Acceptance: every public status has a tested valid transition and UI state.

### API-01 — Make CORS match the supported topology

- For split-origin deployments, configure allowed origins/methods from validated
  settings and include POST/PATCH/DELETE/OPTIONS.
- For same-origin-only support, remove misleading VITE_API_BASE_URL guidance.
- Acceptance: documented topology passes read and mutation browser tests without
  wildcard origins.

### PERF-01 — Add bounded collection APIs

- Introduce limit/cursor or page parameters for Spools, Prints and catalogs.
- Return total/next metadata where UI needs it.
- Update search/filter query keys and add realistic load tests.
- Acceptance: no list response or render grows unbounded by default.

### PERF-02 — Split route bundles

- Lazy-load G-code, QR scanner, Settings, Analytics and detail/form routes.
- Keep Inventory shell/data path in the initial chunk.
- Acceptance: build has no unexplained chunk warning and before/after compressed
  sizes plus route-load behavior are recorded.

### REL-02 / REL-03 — Harden G-code concurrency and I/O

- Move upload filesystem work off the async event-loop thread.
- Add per-upload single-flight/locking for parse and time cache generation, or
  unique temp files with safe winner selection.
- Limit concurrent expensive analyses.
- Acceptance: slow-filesystem and simultaneous-request tests do not block health
  responses, corrupt caches or return spurious 500s.

### DATA-01 / REL-04 — Strengthen persistence policy

- Mirror durable max/format invariants in migrations where appropriate.
- Decide and document SQLite WAL, busy timeout and supported concurrency.
- Add concurrent start/finish/weight tests and a destructive-migration backup
  note for Location removal.
- Acceptance: direct/import writes cannot violate declared invariants and
  expected concurrent use does not produce unhandled lock errors.

### TEST-01 / TEST-02 — Enforce and broaden quality gates

- Add CI for clean install, migrations, 443+ backend tests, 274+ frontend tests,
  typecheck, build and Chromium smoke.
- Add lint/format, coverage, dependency and automated accessibility checks.
- Add E2E for first Spool, Print create/start/finish, archive confirmation and
  real small G-code upload; language switching and persistence are now covered.
- Acceptance: required checks run on each change and publish useful failure
  artifacts.

### ARCH-01 — Decompose high-change modules

- Split GCodeUploadPage into workflow/state and focused panels.
- Split parser/time helpers by responsibility without changing bounded behavior.
- Reformat/decompose PrintJobForm and PrintJobService.
- Preserve tests before moving behavior.
- Acceptance: module boundaries are named by responsibility and no workflow
  regression occurs.

## P3 — Low

### OBS-01 — Add operational observability

- Add structured logs, request IDs, latency/error metrics and health details for
  database and upload capacity without leaking paths or contents.
- Acceptance: an operator can distinguish API, DB, disk and parser failures from
  logs/health output.

### DEP-01 — Lock Python environments

- Produce reviewed pinned constraints/lock data while retaining intentional
  top-level requirements.
- Acceptance: two clean installs resolve identical Python package versions.

### UX-04 — Make G-code analysis resumable or explicitly temporary

- If retaining files, offer recent analyses/resume by upload ID with deletion.
- Otherwise delete on expiry/navigation according to a clearly stated policy.
- Acceptance: UI behavior and storage lifetime no longer contradict each other.

# Recommended Execution Plan

## Wave 1 — Release, safety and core flows

1. REL-01 clean-host verification gate — COMPLETE.
2. FUN-01 visible Print save failures — COMPLETE.
3. STO-01 bounded upload lifecycle — COMPLETE.
4. OPS-01 private-Pi operations and trust-boundary runbook — COMPLETE.

**WAVE 1 — COMPLETE (2026-09-12).**

Exit gate:

- clean checkout passes every current automated gate;
- no silent core mutation failure;
- uploads cannot grow without policy;
- a clean Pi can be installed, started, upgraded, backed up and restored from
  tracked documentation;
- public ingress is disabled unless authentication/authorization is promoted to
  a P0 prerequisite and implemented.

## Wave 2 — UX consistency and accessibility

1. I18N-01/A11Y-01 language completion — COMPLETE (2026-09-13).
2. Accessibility: contrast, semantics and interaction primitives.
3. UX-01 catalog onboarding.
4. Mobile UX and route recovery.
5. Application states and feedback consistency.
6. SEC-01 authentication as low-priority defensive hardening for the supported
   single-user trusted LAN/Tailnet model. Promote it only for public exposure,
   an untrusted network or multiple untrusted users.

Exit gate:

- empty-DB first-use works in browser;
- intended language and HTML language agree;
- core routes pass keyboard and automated accessibility checks;
- primary navigation contains only honest destinations;
- 320/390 px product screenshots are reviewed in both themes/languages.

## Wave 3 — Scale and architectural health

1. PERF-01 pagination.
2. PERF-02 route splitting.
3. REL-02/REL-03 G-code I/O/concurrency.
4. DATA-01/REL-04 persistence concurrency.
5. ARCH-01 decomposition.
6. API-01 topology-aligned CORS.

Exit gate:

- bounded list/upload/analysis behavior under load;
- no build chunk warning without a documented exception;
- concurrent lifecycle/cache tests pass;
- supported deployment topology passes mutations end to end.

## Wave 4 — Continuous quality and polish

1. TEST-01/TEST-02 CI and E2E breadth.
2. OBS-01 observability.
3. DEP-01 reproducibility.
4. UX-04 G-code history/temporary policy.

Exit gate:

- release gates are automatic;
- production failures are diagnosable;
- dependency resolution is reproducible;
- G-code UX matches its retention model.
