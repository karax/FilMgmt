# Wave 2 — Product UX & Onboarding

## Scope and product decisions

Closure validation covers browser-only first use, Settings → Catalogs,
representative pt-BR/en behavior, product feedback, mobile usability, and
removing the Analytics placeholder from primary navigation. Inventory remains
home; the useful inventory Dashboard and the existing Analytics route/code are
preserved. No Analytics feature was built.

Manufacturers and Materials use the existing CRUD APIs and validation. Deletion
is permitted only for unused entries; references from Spools remain protected.
There is no catalog archive API, so no archive semantics were invented.
Location was removed before this wave. `store_name` is purchase-store data;
storage hints can be written in Notes. No Location catalog was recreated.

Authentication/public-network hardening: **DEFERRED** while deployment remains
local-first, single-user, trusted LAN/Tailnet. Full accessibility remediation:
**DEFERRED** to a later polish/accessibility phase. Neither is resolved.
Analytics: **NOT IMPLEMENTED**. Wave 3: **NOT STARTED**.

## Workstreams

- W2-01: manufacturer/material browser CRUD, density help, protected-delete
  feedback, empty-catalog recovery link from New Spool.
- W2-02: equivalent catalog resources in pt-BR/en; first-run Inventory copy
  now uses the existing translations. Entity names and stored currency remain
  unchanged when switching locale.
- W2-03: catalog loading/error/retry, actionable empty states, Print Tracker
  creation action and explicit explanation for blocked Start Print.
- W2-04: mobile Inventory defaults to Grid when no preference exists; existing
  responsive forms and bounded lifecycle dialogs are validated in Chromium.
- W2-05: Analytics removed from primary desktop/mobile navigation; real
  Dashboard preserved; Inventory remains home.

## Reproducible validation

Use Node 24.15+ in the 24.x line (`package.json#engines`); closure runtime:
24.20.0. Node 20 is incompatible with the locked jsdom/undici stack.
`npm run typecheck` now runs `tsc -b`, including referenced projects.

`npm run test:e2e:wave2` starts a freshly migrated temporary SQLite backend on
18002 and a frontend build on 15173. It refuses existing listeners. The first
test creates catalogs and Spools through browser controls, then checks edits,
allowed/protected deletion and language persistence. The following tests cover
390×844 and critical 320×844 flows, including multi-Spool cost, Start/Finish,
manual QR fallback and real G-code upload/analysis. Existing smoke, bilingual
and Print save-error tests run afterward against this isolated environment.

Set `FCC_WAVE2_SCREENSHOTS=1` to capture only Wave 2 documentation images.
Diagnostic screenshots/traces stay in ignored `frontend/test-results`.
The real user database is never reset or used by this runner.

## Browser validation results

- Browser-only onboarding: PASS against a freshly migrated temporary SQLite
  database. Chromium created a Manufacturer, Material and two Spools through
  product controls, confirmed Inventory, exercised catalog edits, protected and
  allowed deletion, and verified pt-BR/en persistence.
- 390×844: PASS for Inventory, Catalogs, New Spool, Spool Details, New Print,
  multi-Spool estimated cost, Start/Finish Print, QR manual fallback, G-code
  upload/analysis and Settings.
- 320×844: PASS for the critical Catalogs, New Spool, New Print and Finish Print
  checks. The scenario also retained readable Inventory/Spool navigation.
- Bugs found and fixed during closure: long Inventory card content could impose
  an intrinsic grid width; switching directly between open catalog editors kept
  the first record's local form state; the production-preview E2E proxy did not
  forward `/api`. Focused regression tests and the real-browser matrix now pass.

Targeted frontend result: 26/26 Catalogs, New Spool and i18n tests passed. Wave
2 Playwright result: 3/3 passed with one worker. The existing browser files were
then run serially to respect host limits: 11/11 i18n, 2/2 Print save-error and
8/8 smoke tests passed (21/21 total).

## Final gates

- Backend: `pytest` 488/488 PASS; `python -m compileall app` PASS; `alembic
  check` PASS with no new upgrade operations.
- Frontend: focused 26/26 PASS; full Vitest 324/324 PASS; `npm run typecheck`
  PASS; `npm run build` PASS.
- Browser: doctor PASS on aarch64 with Node 24.20.0, Playwright 1.62.1 and
  Chromium 153; Wave 2 E2E 3/3 PASS; existing browser suite 21/21 PASS.
- Documentation: the three materially changed screenshots were reviewed; the
  manual PDF was regenerated (2,617,673 bytes), validated and included in the
  production frontend build.
- Repository: `git diff --check` PASS; temporary Playwright reports and isolated
  databases were removed. Existing user data/backups were not modified.

## Remaining UX debt

Full contrast, keyboard/focus and form-error accessibility remediation remains
deferred. Catalog list pagination, Analytics, route splitting and architecture
work remain outside Wave 2. The retained Analytics URL is not a primary product
destination. User-entered notes/catalog names are not translated.

Schema changes: **NO**. Migrations created: **NO**.
