# Improvement Backlog

> Status: synthesized from the completed full-system audit on 2026-09-03.
> Priority: P0 release blocker, P1 high, P2 medium, P3 low.

## P0 — Critical

### REL-01 — Make the delivered source reproducible

- Track every intended runtime, migration, test, tooling and documentation file.
- Explicitly review all 55 currently untracked paths; do not use broad cleanup.
- Build a fresh checkout or git archive, create a new database, run all
  migrations, backend/frontend tests, typecheck, build and Chromium smoke.
- Acceptance: git status contains no accidentally omitted product files and the
  clean-checkout gate passes without borrowing files from the current worktree.

## P1 — High

### SEC-01 — Establish the application trust boundary

- Decide whether the supported mode is trusted single-user LAN or authenticated
  multi-user/network service.
- Protect all reads and mutations; require stronger authorization for catalog
  mutation, archive/delete and uploads.
- Make docs/OpenAPI exposure environment-controlled and document trusted hosts.
- Acceptance: anonymous clients cannot access protected data or mutate state;
  authorization tests cover destructive and upload endpoints.

### FUN-01 — Show Print Job save failures

- Consume submitError in PrintJobForm.
- Map 409, 422 and network errors into localized form/field feedback.
- Preserve values, focus the first invalid field and prevent duplicate submit.
- Acceptance: create/edit component tests prove visible localized recovery for
  all three failure classes.

### I18N-01 / A11Y-01 — Complete language behavior

- Move all hard-coded user and accessible copy into both locale resources.
- Translate raw statuses in Spool/Print summaries.
- Set document.documentElement.lang at initialization and language changes.
- Add locale key-parity and core-route leakage tests.
- Acceptance: pt-BR and English passes contain no unintended opposite-language
  copy and the DOM language matches the selected locale.

### A11Y-02 — Correct light-theme contrast

- Split decorative accent from an accessible accent-text/focus token.
- Reach at least 4.5:1 for normal text and 3:1 for non-text focus indicators.
- Recheck links, FIL codes, eyebrows, selected view text and small dashboard
  actions in light mode.
- Acceptance: measured pairs pass WCAG AA and visual snapshots are reviewed.

### STO-01 — Add a G-code storage lifecycle

- Configure upload TTL and a total storage quota in addition to per-file size.
- Add safe cleanup for upload, metadata, parse and time sidecars.
- Expose delete/recent-upload UX only if resumable analysis is desired.
- Report disk-full/quota errors clearly and add scheduled/manual cleanup docs.
- Acceptance: tests cover expiry, quota rejection, partial sidecars, concurrent
  cleanup and no deletion outside the configured directory.

### OPS-01 — Define supported production operations

- Provide a non-reload API service, built frontend serving/reverse proxy and
  environment reference.
- Document HTTPS for remote QR camera access.
- Document coordinated backup/restore for SQLite and upload storage.
- Add upgrade/rollback steps and a system startup/health procedure.
- Acceptance: a clean host can be installed, restarted, backed up and restored
  by following only the runbook.

### UX-01 — Unblock clean-install catalog onboarding

- Add Manufacturer/Material management in Settings, or a first-run wizard that
  safely runs/validates seed data.
- Replace “Create first” dead-end messages with direct actions.
- Preserve referential-integrity warnings when editing/deleting catalog items.
- Acceptance: a browser-only user can go from an empty DB to the first Spool.

### DOC-01 — Rewrite the root README

- Rebuild state/routes/API/limitations from current runtime.
- Remove Location and implemented-feature claims that are no longer true.
- Correct relative API behavior and the nonexistent visual install command.
- Link the G-code, QR, browser and Print Tracker docs.
- Acceptance: every documented command is executed in a clean-checkout gate.

## P2 — Medium

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
- Add E2E for first Spool, Print create/start/finish, archive confirmation,
  language switch and real small G-code upload.
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

1. REL-01 source reproducibility.
2. FUN-01 visible Print save failures.
3. I18N-01/A11Y-01 language completion.
4. STO-01 upload lifecycle.
5. SEC-01 trust boundary.
6. DOC-01 plus minimum OPS-01 release/runbook documentation.

Exit gate:

- clean checkout passes every current automated gate;
- no silent core mutation failure;
- intended language and HTML language agree;
- uploads cannot grow without policy;
- supported network exposure is explicitly protected/documented.

## Wave 2 — UX consistency and accessibility

1. UX-01 catalog onboarding.
2. A11Y-02 contrast.
3. A11Y-03/A11Y-04 primitives.
4. IA-01 Analytics decision.
5. UX-02/UX-03 mobile and route recovery.
6. FUN-02/FUN-03 state consistency.

Exit gate:

- empty-DB first-use works in browser;
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
