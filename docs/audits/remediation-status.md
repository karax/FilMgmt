# Filament Command Center — Audit Remediation Status

## Snapshot

- Date: 2026-09-17
- Branch: `refactor`
- Commit: `c01c07bb77293b8ac043039ad51fc7547e951d8d`
- Tag at `HEAD`: `wave-1-complete`
- Working tree before this report: dirty, with 76 entries (74 tracked
  modifications and 2 untracked files).
- Working-tree classification: completed Wave 2.1 i18n remediation that has
  not yet been committed. The changes cover locale resources, user-facing
  components, i18n tests, the bilingual Playwright matrix, guide wording,
  screenshots/PDF, and the i18n closure report. No unrelated or unknown change
  class was identified.
- This report adds one documentation file. It does not make the Wave 2.1 work
  part of `HEAD`; a clean checkout of `c01c07b` contains Wave 1, not the current
  i18n working-tree remediation.

Historical-document differences reconciled here:

- `rel-01-clean-checkout-validation.md` ends at **CONDITIONALLY READY** because
  it predates the closing commit. `c01c07b` contains its README and
  self-contained smoke corrections, so that condition is now satisfied.
- The audit master table and backlog mark I18N-01/A11Y-01 complete, while the
  final paragraph of the audit still calls localization later work. Current
  code, tests, and `i18n-consistency.md` support the completed status.
- SEC-01 is P3 in the audit's supported private mode but P2 in the backlog. The
  current recommendation is low priority/P3 for the present single-user
  trusted LAN/Tailnet, with automatic promotion to P1 on an untrusted network
  or multiple untrusted users and to P0 before public ingress.
- REL-03's original text says a fixed cache temporary path has no coordination.
  STO-01 added shared write locks and active-operation protection, preventing
  the writer race, but it did not add single-flight computation. REL-03 is
  therefore PARTIAL.

## Executive Status

- Wave 1 engineering work is complete. REL-01, FUN-01, STO-01, and the DOC-01
  portion of OPS-01 are verified in the current `HEAD`.
- OPS-01 is implemented and running on the real Raspberry Pi. Caddy, user
  services, linger, daily verified backups, LAN serving, and private Tailscale
  Serve are active. A post-install reboot, external-device paths, real camera,
  and off-device backup still need physical confirmation.
- Wave 2.1 is implemented and verified in the current working tree, but is not
  committed. The current engineering phase is Wave 2.2 Accessibility.
- No unconditional P0/P1 engineering finding remains for the supported
  single-user trusted LAN/Tailnet model. Public Internet exposure remains
  prohibited and would immediately promote SEC-01 to a P0 gate.
- The most material current product risks are browser-only first-use catalog
  onboarding, accessibility contrast/focus/error coverage, absent CI
  enforcement, and unbounded list/concurrency behavior as data or use grows.

## Status Summary

Each of the 30 audit IDs is counted once, even where the backlog combines IDs
into one implementation block.

| Wave | Total | Verified Complete | Manual Validation | Partial | Not Started | Other |
|---|---:|---:|---:|---:|---:|---:|
| Wave 1 | 5 | 4 | 1 | 0 | 0 | 0 |
| Wave 2 | 12 | 2 | 0 | 3 | 7 | 0 |
| Wave 3 | 8 | 0 | 0 | 2 | 6 | 0 |
| Wave 4 | 5 | 0 | 0 | 4 | 1 | 0 |
| **Total** | **30** | **6** | **1** | **9** | **14** | **0** |

`Other` would contain SUPERSEDED, NO LONGER APPLICABLE, or NEEDS RECHECK.
None is required by the current evidence.

## Latest Validation Baseline

| Gate | Latest supported result | Source and repository alignment |
|---|---|---|
| Backend full suite | **488/488 PASS** | OPS-01 closure, 2026-09-12; backend is unchanged by the current frontend-only i18n working tree. |
| Frontend full suite | **315/315 PASS** | OPS-01 closure, 2026-09-12. Wave 2.1 reports its full gate as passing but does not preserve a newer numeric total, so 315 is the latest documented full-suite count. |
| Targeted i18n | **4/4 PASS** | Re-run 2026-09-17 against the current working tree: default/switch/persistence, invalid locale, recursive key parity, and localized status display. |
| TypeScript typecheck | **PASS** | OPS-01 closure, 2026-09-12. The Wave 2.1 completion record reports PASS, although its Markdown closure omits the raw gate log. |
| Production build | **PASS** | OPS-01 closure, 2026-09-12. The Wave 2.1 completion record reports PASS; the served current `dist`/manual were also validated on the Pi. |
| Alembic drift | **PASS** | OPS-01 closure; current deep check on 2026-09-17 reports revision `f2a8c7d190b4`. |
| Chromium | **PASS** | OPS-01 production-like smoke 8/8; Wave 2.1's current spec contains 11 bilingual/persistence/mobile scenarios and its closure reports the matrix passed. Real Pi HTTPS/LAN smokes later passed Inventory, G-code, Scan, Settings/manual, and mobile routes. |
| SQLite | **PASS** | Re-run 2026-09-17: `integrity_check=ok`, `foreign_key_check=0`, revision `f2a8c7d190b4`. |
| Restore drill | **PASS** | OPS-01 controlled temporary drill, 2026-09-12: representative canonical records survived, integrity was `ok`, and FK violations were zero. |
| Live operations | **PASS with manual items below** | On 2026-09-17 backend/web services are active+enabled with zero restarts, linger is enabled, local and LAN HTTP return 200, Tailscale Serve is Tailnet-only, and the daily backup timer has produced four database+manifest pairs. |

The older 443/274, 448/313, and 479/315 totals remain historical milestones,
not the current baseline.

## Audit Finding Inventory

`Original priority` preserves the first audit classification and shows later
challenge-review changes where applicable. `Documented status` summarizes the
historical audit/backlog rather than treating it as proof.

| ID | Title | Original priority | Area | Wave | Dependencies | Documented status |
|---|---|---|---|---:|---|---|
| REL-01 | Make the delivered source reproducible | P0 gate | Delivery | 1 | None; gate for later work | COMPLETE/RESOLVED after 2026-09-07, although the pre-commit closure report itself ends conditionally |
| FUN-01 | Show Print Job save failures | P1 | Core flow | 1 | REL-01 release gate | RESOLVED 2026-09-09 |
| STO-01 | Add a G-code storage lifecycle | P1 | Reliability | 1 | REL-01; policy consumed by OPS-01 | RESOLVED 2026-09-09 |
| OPS-01 | Define supported production operations | P1 | Operations | 1 | REL-01 and final STO-01 policy | RESOLVED 2026-09-12 |
| DOC-01 | Align runtime/production documentation | P1 | Documentation | 1 | Consolidated into OPS-01 | CONSOLIDATED/RESOLVED with OPS-01 |
| SEC-01 | Establish the application trust boundary/authentication | P1 originally; P3 private/P0 public after review | Security | 2 | OPS-01 trust model; deployment/user model decides promotion | Open P2 in backlog; P3 private/P0 gate in audit |
| I18N-01 | Complete pt-BR/English consistency | P1 originally, then P2 | i18n | 2 | Existing locale architecture | COMPLETE/RESOLVED 2026-09-13 |
| A11Y-01 | Synchronize document language with locale | P1 originally, then P2 | Accessibility | 2 | I18N-01 locale validation | COMPLETE/RESOLVED 2026-09-13 |
| A11Y-02 | Correct light-theme contrast | P1 originally, then P2 | Accessibility | 2 | Token/visual review | Open |
| UX-01 | Unblock clean-install catalog onboarding | P1 originally, then P2 | Onboarding | 2 | OPS-01 setup contract; existing catalog APIs | Open |
| A11Y-03 | Standardize accessible dialog focus | P2 | Accessibility | 2 | Shared dialog primitive | Open |
| A11Y-04 | Associate form and submit errors | P2 | Accessibility | 2 | Shared field primitive; preserve FUN-01 behavior | Open |
| IA-01 | Resolve Analytics navigation | P2 | IA | 2 | Product-scope decision | Open |
| UX-02 | Improve narrow-screen header/inventory behavior | P2 | Mobile | 2 | Settled bilingual copy | Open |
| UX-03 | Add branded route/error recovery | P2 | Navigation | 2 | Settled bilingual copy/router decision | Open |
| FUN-02 | Correct Inventory loading count | P2 | Inventory | 2 | Existing i18n loading copy | Open |
| FUN-03 | Reconcile Print lifecycle states | P2 | Lifecycle | 2 | Domain transition decision | Open |
| PERF-01 | Add bounded collection APIs | P2 | Performance | 3 | API/UI pagination contract | Open |
| PERF-02 | Split route bundles | P2 | Frontend performance | 3 | Route/error loading boundaries | Open |
| REL-02 | Move upload I/O off the async event loop | P2 | Backend reliability | 3 | STO-01 upload lifecycle | Open |
| REL-03 | Coordinate G-code cache concurrency | P2 | Backend reliability | 3 | STO-01 activity/storage locks | Open; audit text predates partial STO-01 mitigation |
| DATA-01 | Mirror durable API invariants in storage | P2 | Data | 3 | Invariant/migration policy | Open |
| REL-04 | Define SQLite concurrency policy | P2 | Database reliability | 3 | DATA-01 policy and deployment limits | Open |
| ARCH-01 | Decompose high-change modules | P2 | Maintainability | 3 | Behavior tests; preferably stable Wave 2 UI | Open |
| API-01 | Align CORS with supported topology | P2 | Deployment | 3 | OPS-01 same-origin decision | Open |
| TEST-01 | Enforce quality gates | P2 | Quality | 4 | REL-01/OPS-01 commands; chosen CI | Open |
| TEST-02 | Broaden end-to-end coverage | P2 | E2E | 4 | Stable primary flows/accessibility primitives | Open, with updated text acknowledging bilingual coverage |
| OBS-01 | Add operational observability | P3 | Observability | 4 | OPS-01 health/journald foundation | Open |
| DEP-01 | Lock Python environments | P3 | Reproducibility | 4 | REL-01 install evidence | Open |
| UX-04 | Make G-code analysis resumable or explicitly temporary | P3 | G-code UX | 4 | STO-01 retention contract | Open |

## Wave 1

| ID | Finding | Status | Evidence | Remaining validation |
|---|---|---|---|---|
| REL-01 | Make the delivered source reproducible | **VERIFIED COMPLETE** | Commit `4370ec9` added the omitted 107 paths. The clean-clone report proves fresh installs, empty migration, SQLite, tests, build, manual, first-use, G-code, QR, and hidden-dependency checks. Closing commit `c01c07b` tracks the validated README and self-contained `frontend/e2e/smoke.spec.ts` fixes. | None for the Wave 1 release. Python transitive locking remains the separate DEP-01 finding. |
| FUN-01 | Show Print Job save failures | **VERIFIED COMPLETE** | `printSaveErrors.ts`, `PrintJobForm`, mutation hooks, and Create/Edit pages handle structured codes, nested spool rows, 409/422/network/5xx, stable row keys, retained values, retry, focus, `aria-invalid`, and `aria-describedby`. Closure records 39 new integration, 28 targeted Print, 11 backend API, and full-suite gates. | None within FUN-01. Broader form/dialog accessibility remains A11Y-03/A11Y-04. |
| STO-01 | Add a G-code storage lifecycle | **VERIFIED COMPLETE** | Current defaults are 100 MiB/file, 30-day retention, 2 GiB total, one-hour stale-temp threshold, automatic cleanup and retention enabled. Cleanup units, active protection, streaming quota checks, safe path/symlink rules, structured 507 feedback, CLI `--dry-run`, frontend copy, and docs/tests exist. | None within STO-01. Cross-process/single-flight analysis remains REL-03. |
| OPS-01 | Define supported production operations | **IMPLEMENTED — MANUAL VALIDATION PENDING** | Runbook, env example, loopback Uvicorn/Caddy units, backup timer, health/deep checks, online backup, guarded restore, update/rollback, production Playwright, and operations tests exist. Controlled restore and routing passed. On the real Pi, Caddy and services are active+enabled, linger is on, LAN/Tailscale serving works, and scheduled backups are running. | Controlled post-install reboot; external LAN and Tailnet device checks; real-phone camera; copy a verified backup off the microSD. |
| DOC-01 | Align runtime/production documentation | **VERIFIED COMPLETE** | Consolidated into OPS-01. README links the canonical runbook; setup, current routes, `npm ci`, migrations/seeds, browser tooling, private topology, and public-ingress prohibition are tracked. | None. |

## Wave 1 Closure Assessment

- Is Wave 1 engineering work complete? **YES.**
- Are manual validations pending? **YES**, limited to the physical/operational
  items listed below.
- Is it safe to proceed to Wave 2? **YES**, for the documented single-user
  trusted LAN/Tailnet deployment. Physical OPS validation should be scheduled
  before relying on unattended recovery, but does not block frontend
  engineering.

## Wave 2

| ID | Finding | Priority | Status | Evidence | Remaining work |
|---|---|---|---|---|---|
| SEC-01 | Establish the application trust boundary/authentication | P3 current; conditional P1/P0 | **PARTIAL** | OPS-01 binds FastAPI to loopback, uses same-origin Caddy, private Tailnet/LAN profiles, and explicitly prohibits public ingress. No application authentication, authorization, role separation, or docs/OpenAPI control exists. | Keep private boundary. Implement auth only when the deployment becomes public, untrusted, or multi-user. |
| I18N-01 | Complete pt-BR/English consistency | P2 | **VERIFIED COMPLETE** | Static locale resources, recursive parity, localized bounded statuses/errors/actions, locale-aware formatters, preserved entity/currency semantics, 11-scenario browser matrix, and 4/4 current targeted tests. | Review and commit the current Wave 2.1 working tree so the release HEAD includes it. |
| A11Y-01 | Synchronize document language with selected locale | P2 | **VERIFIED COMPLETE** | `resolveStoredLanguage` safely defaults to pt-BR; initial and changed locale update `<html lang>`; persistence and invalid values are tested. | Same release-integration action as I18N-01. |
| A11Y-02 | Correct light-theme contrast | P2 | **NOT STARTED** | Light accent remains `#00a6a6` and is still used for small text/focus. No separate accessible text/focus token or new contrast evidence exists. | Implement tokens, measure required pairs, and review snapshots. |
| UX-01 | Unblock clean-install catalog onboarding | P2 | **NOT STARTED** | Manufacturer/Material APIs and CLI seeds exist, but New Spool still disables submission for empty catalogs and no catalog UI/wizard exists. | Browser-only catalog management or first-run onboarding with safe referential-integrity behavior. |
| A11Y-03 | Standardize accessible dialogs/focus | P2 | **PARTIAL** | Print dialogs have `aria-modal` and initial cancel focus; destructive Spool/Print dialogs exist. There is no shared primitive, focus trap/inert background, consistent Escape handling, or trigger restoration. | Implement and migrate a tested dialog primitive. |
| A11Y-04 | Associate form and submit errors | P2 | **PARTIAL** | FUN-01 associates/focuses Print save errors, and Finish fields use `aria-invalid`/`aria-describedby`. This is not a global FormField contract and Spool/other forms remain inconsistent. | Shared field primitive and screen-reader/keyboard tests across Spool and Print flows. |
| IA-01 | Resolve Analytics navigation | P2 | **NOT STARTED** | `/analytics` remains a primary navigation route rendering `PagePlaceholder`. | Hide, honestly label as preview, or deliver minimum useful content. |
| UX-02 | Improve narrow-screen header/inventory behavior | P2 | **NOT STARTED** | Translation-length smoke confirms no document overflow, but it does not fix title truncation or table-first horizontal data discovery. | Compact header/theme control and mobile inventory presentation. |
| UX-03 | Add branded route/error recovery | P2 | **NOT STARTED** | Router remains eager and has no catch-all or `errorElement`. | Localized 404/error route with safe navigation. |
| FUN-02 | Correct Inventory loading count | P2 | **NOT STARTED** | Current `InventoryToolbar` still maps `count === null` to `common.retry`. | Render a loading placeholder or suppress the count. |
| FUN-03 | Reconcile Print FAILED/CANCELLED states | P2 | **NOT STARTED** | Enums, DB check, badges and read-only rendering exist, but no API/UI transition creates either status. | Implement tested transitions and lock/weight semantics, or remove them from active contracts. |

## Wave 3

| ID | Finding | Priority | Status | Evidence | Remaining work |
|---|---|---|---|---|---|
| PERF-01 | Add bounded collection APIs | P2 | **NOT STARTED** | Spool, Print, and catalog APIs expose filters but no limit/cursor/page contract. | Bounded API/UI pagination and realistic load tests. |
| PERF-02 | Split route bundles | P2 | **NOT STARTED** | Router imports every page eagerly; no route `lazy`/Suspense boundary exists. | Lazy-load noncritical routes and record bundle/route behavior. |
| REL-02 | Move upload I/O off the async event loop | P2 | **NOT STARTED** | Upload endpoint still awaits a coroutine that performs synchronous open/write/flush/fsync work. | Thread/offload filesystem operations and add slow-storage health-concurrency tests. |
| REL-03 | Coordinate G-code cache concurrency | P2 | **PARTIAL** | STO-01 added active-operation tracking, a shared storage lock, atomic cache replacement, and cleanup protection. Concurrent parse/time calls can still duplicate expensive computation; coordination is process-local and no analysis concurrency limit exists. | Per-upload single-flight/cross-process-safe strategy and simultaneous-request tests. |
| DATA-01 | Mirror durable API invariants in storage | P2 | **NOT STARTED** | Existing DB checks cover core positivity/status rules, but audited maxima/format rules remain API-only. | Decide durable invariants and add migration/import validation where justified. |
| REL-04 | Define SQLite concurrency policy | P2 | **NOT STARTED** | Engine enables foreign keys/check-same-thread handling but no explicit WAL or busy-timeout policy is present. | Decide/document WAL/busy policy and test concurrent lifecycle writes. |
| ARCH-01 | Decompose high-change modules | P2 | **NOT STARTED** | G-code page/parser and Spool/Print modules remain concentrated; i18n changes did not move ownership boundaries. | Behavior-preserving decomposition after relevant UX work stabilizes. |
| API-01 | Align CORS with supported topology | P2, suggested P3 in current mode | **PARTIAL** | OPS-01 established and tested the same-origin production model, so production mutations do not depend on CORS. Backend still allows only GET for listed dev origins while `VITE_API_BASE_URL` still advertises a split-origin escape hatch. | Declare same-origin-only and remove misleading split-origin support, or implement validated configurable origins/methods. |

## Wave 4

| ID | Finding | Priority | Status | Evidence | Remaining work |
|---|---|---|---|---|---|
| TEST-01 | Enforce quality gates | P2 | **PARTIAL** | Clean-clone procedure, large local suites, browser doctor, production Playwright, and reproducible docs tooling exist. There is still no CI config, lint/format gate, coverage floor, dependency scan, or automated accessibility gate. | Add required automated gates with useful artifacts. |
| TEST-02 | Broaden end-to-end coverage | P2 | **PARTIAL** | Smoke covers production routing/mobile/manual; FUN-01 adds real-route failure/retry; Wave 2.1 adds bilingual/persistence/mobile scenarios. Primary Spool/Print lifecycle mutations, archive, real upload, and keyboard dialogs remain absent from the standard E2E gate. | Add the missing mutation/upload/keyboard journeys without real-data coupling. |
| OBS-01 | Add operational observability | P3 | **PARTIAL** | OPS-01 adds journald, quick health, deep SQLite checks, backup failures, and storage inspection. Structured request logs/IDs, latency/error metrics, and capacity-aware health details are not implemented. | Add lightweight structured diagnostics appropriate to a Pi. |
| DEP-01 | Lock Python environments | P3 | **NOT STARTED** | Clean installs are proven, but Alembic and SQLAlchemy remain broad ranges and no reviewed constraints/lock file exists. | Produce and verify pinned transitive constraints. |
| UX-04 | Make G-code analysis resumable or explicitly temporary | P3 | **PARTIAL** | STO-01 now gives storage an explicit 30-day retention/quota/cleanup policy. The page still owns the upload ID only in memory and exposes no recent-history, resume, or delete flow. | Make temporary behavior explicit in user UI or add bounded history/resume/delete. |

## Cross-Wave Remediation

| Finding | Original Wave | Remediation source | Current status |
|---|---|---|---|
| DOC-01 | Wave 1 | OPS-01 runbook and README alignment | **VERIFIED COMPLETE** |
| SEC-01 | Wave 2 | OPS-01 private same-origin topology and public-ingress prohibition | **PARTIAL** |
| A11Y-04 | Wave 2 | FUN-01 Print error association/focus | **PARTIAL** |
| API-01 | Wave 3 | OPS-01 same-origin Caddy topology | **PARTIAL** |
| REL-03 | Wave 3 | STO-01 active-operation/storage locks and atomic cache writes | **PARTIAL** |
| TEST-01 | Wave 4 | REL-01 clean-clone gate and OPS-01 production gate tooling | **PARTIAL** |
| TEST-02 | Wave 4 | REL-01 smoke, FUN-01 real-route errors, OPS-01 production config, Wave 2.1 bilingual E2E | **PARTIAL** |
| OBS-01 | Wave 4 | OPS-01 journald/health/deep checks | **PARTIAL** |
| UX-04 | Wave 4 | STO-01 retention/quota/cleanup policy | **PARTIAL** |

## Resolved Findings

- REL-01 — Make the delivered source reproducible.
- FUN-01 — Show Print Job save failures.
- STO-01 — Add a G-code storage lifecycle.
- DOC-01 — Align runtime/production documentation.
- I18N-01 — Complete pt-BR/English consistency.
- A11Y-01 — Synchronize document language with selected locale.

OPS-01 is deliberately excluded from this list because its principal status is
IMPLEMENTED — MANUAL VALIDATION PENDING.

## Partially Resolved Findings

- SEC-01 — private network boundary exists; application auth does not.
- A11Y-03 — modal semantics/initial focus exist; full focus behavior does not.
- A11Y-04 — Print-specific association exists; global forms remain inconsistent.
- API-01 — production is same-origin; optional split-origin contract is stale.
- REL-03 — writer/cleanup races are reduced; duplicate computation remains.
- TEST-01 — strong local gates exist; enforcement/quality classes are absent.
- TEST-02 — browser breadth improved; primary mutation journeys remain.
- OBS-01 — operations diagnostics exist; app-level structured telemetry does not.
- UX-04 — storage lifetime is explicit operationally; UI continuity is absent.

## Not Started Findings

- A11Y-02 — light-theme contrast.
- UX-01 — browser-only catalog onboarding.
- IA-01 — Analytics navigation honesty.
- UX-02 — narrow-screen header/inventory behavior.
- UX-03 — branded 404/error recovery.
- FUN-02 — Inventory loading count.
- FUN-03 — FAILED/CANCELLED lifecycle contract.
- PERF-01 — pagination/bounded collections.
- PERF-02 — route splitting.
- REL-02 — async upload I/O offload.
- DATA-01 — durable invariant policy.
- REL-04 — SQLite concurrency policy.
- ARCH-01 — high-change module decomposition.
- DEP-01 — Python transitive lock/constraints.

## Manual Validations Still Outstanding

| Item | Why manual | Risk | Required action | Expected result |
|---|---|---|---|---|
| Post-install reboot/autostart | Services and linger were enabled after the current boot (boot 2026-09-11; install/start 2026-09-13). | Medium: unattended recovery is not physically proven. | Schedule a controlled `sudo reboot`; reconnect and run `systemctl --user status filament-command-center.service filament-command-center-web.service filament-command-center-backup.timer`, then health checks. | All units active/enabled without an interactive login; health is overall healthy. |
| External trusted-LAN device | Curl to the Pi's LAN address passes on the Pi, but Codex cannot prove the Wi-Fi client path. | Low–Medium: AP/client isolation could block users. | From a device on the same trusted Wi-Fi, discover the current DHCP address with `hostname -I` and open `http://<LAN-IP>:8080/`. | Inventory/API/manual load; no router port-forwarding is required. |
| External Tailnet device | Serve and TLS work on the Pi, but a separate device path/ACL remains operator-owned. | Low–Medium: Tailnet ACL/device state can differ. | Connect the phone to Tailscale and open the current `https://<hostname>.ts.net/`; test `/settings` and `/scan`. | Valid TLS and Tailnet-only access; Funnel remains off. |
| Real phone camera | Headless Chromium cannot validate physical camera permission/device behavior. | Medium for QR scanning only. | On the Tailnet HTTPS URL, open Scan QR, grant camera permission, and scan a known FCC QR code. | Live preview and local decode work; manual FIL fallback remains available. |
| Off-device verified backup | Four scheduled verified backups exist on the same microSD only. | High under SD/device loss. | Periodically copy a database+manifest pair to another computer/NAS/external drive and re-check SHA-256 plus SQLite integrity there. | At least one recent verified pair survives loss of the Pi/storage device. |

The controlled restore drill is complete; a destructive restore over real user
data is intentionally not a pending acceptance test.

## Current Risk Register

| Risk | Related finding | Current status | Impact | Next action |
|---|---|---|---|---|
| Current Wave 2.1 remediation can be lost or omitted from a release because it is uncommitted. | I18N-01, A11Y-01, REL-01 delivery principle | Complete in working tree, not in `HEAD` | High delivery risk | Review the Wave 2.1 diff and create an intentional commit boundary before new edits. |
| A clean browser-only install cannot create its first Spool without administrator seed/API knowledge. | UX-01 | NOT STARTED | High onboarding impact | Implement catalog onboarding after accessibility. |
| Low-contrast text/focus and incomplete modal/form semantics remain. | A11Y-02/03/04 | NOT STARTED/PARTIAL | Medium–High accessibility impact | Execute Wave 2.2 with measured contrast and reusable dialog/field primitives. |
| Any reachable trusted peer can read or mutate data; public exposure would be unsafe. | SEC-01 | PARTIAL | High if trust boundary changes | Keep LAN/Tailnet controlled; promote auth before untrusted/multi-user/public use. |
| List sizes, upload I/O, cache work, and SQLite write contention have no full growth/concurrency policy. | PERF-01, REL-02/03/04 | NOT STARTED/PARTIAL | Medium availability/latency impact as use grows | Address in Wave 3 with bounded/load/concurrency tests. |
| Local quality gates are not automatically enforced. | TEST-01/02 | PARTIAL | Medium regression/delivery impact | Add CI and broader E2E after core Wave 2 interactions stabilize. |
| Same-SD backups do not cover device/media loss. | OPS-01 | Manual validation pending | High disaster-recovery impact | Establish periodic off-device verified copies. |

## Current Engineering Backlog

Manual-only OPS items are excluded and listed separately above. Priority below
reflects the current private deployment, not public exposure.

| Order | Finding(s) | Current priority | Effort | Status |
|---:|---|---|---|---|
| 1 | A11Y-02 — light-theme contrast | P2 | M | NOT STARTED |
| 2 | A11Y-03/A11Y-04 — dialogs and form errors | P2 | M | PARTIAL |
| 3 | UX-01 — catalog onboarding | P2 | L | NOT STARTED |
| 4 | UX-02/UX-03 — mobile context and route recovery | P2 | M | NOT STARTED |
| 5 | FUN-02 — Inventory loading count | P2 | S | NOT STARTED |
| 6 | IA-01 — Analytics navigation | P2 | S | NOT STARTED |
| 7 | FUN-03 — lifecycle states | P2 | M | NOT STARTED |
| 8 | PERF-01 — bounded collections | P2 | M | NOT STARTED |
| 9 | PERF-02 — route splitting | P2 | M | NOT STARTED |
| 10 | REL-02/REL-03 — G-code I/O/concurrency | P2 | M | NOT STARTED/PARTIAL |
| 11 | DATA-01/REL-04 — persistence policy/concurrency | P2 | M | NOT STARTED |
| 12 | ARCH-01 — module decomposition | P2 | L | NOT STARTED |
| 13 | TEST-01/TEST-02 — CI and E2E breadth | P2 | M | PARTIAL |
| 14 | API-01 — topology-aligned CORS | Suggested P3 in same-origin mode | S | PARTIAL |
| 15 | OBS-01 — observability | P3 | M | PARTIAL |
| 16 | DEP-01 — Python lock/constraints | P3 | S | NOT STARTED |
| 17 | UX-04 — G-code continuity/temporary UX | P3 | M | PARTIAL |
| 18 | SEC-01 — defensive authentication | P3 in current mode | L | PARTIAL |

Suggested priority changes:

- SEC-01: use P3/low priority while the deployment remains one trusted operator
  on controlled LAN/Tailnet; promote exactly when the trust model changes.
- API-01: lower from P2 to P3 if same-origin is declared the only supported
  topology and the misleading override is removed; keep P2 if split origin is
  intended.
- REL-03: STO-01 removed the spurious-writer-failure mechanism, reducing its
  likelihood. Keep the remaining duplicate-work/concurrency-limit work in Wave
  3 rather than treating the old finding as untouched.

## Dependency Map

- Review/commit current I18N-01/A11Y-01 remediation before overlapping Wave 2
  edits. This is release hygiene, not a new product finding.
- A11Y-02 is independent and immediately actionable.
- A11Y-03 and A11Y-04 should share Dialog/FormField primitives; FUN-01 provides
  a proven Print-specific error model to preserve.
- UX-01 is now unblocked: catalog APIs, migrations, seeds, and the production
  setup contract already exist.
- UX-02/UX-03 should consume the settled bilingual copy, which now exists.
- SEC-01 stays last in the current Wave 2 order unless network/user trust changes.
- REL-03 should extend, not replace, STO-01's activity/storage-lock foundation.
- UX-04 should use STO-01's 30-day retention and quota as its product contract.
- TEST-01/TEST-02 can start after the Wave 2 interaction primitives settle, so
  CI/E2E encode the intended flows rather than transient markup.

## Recommended Next Task

- ID: **A11Y-02**
- Title: **Correct light-theme contrast**
- Priority: **P2**
- Effort: **M**
- Reason: it is the first untouched, measurable part of Wave 2.2; it affects
  normal text and focus visibility across the product and can be completed
  without schema/backend changes.
- Dependencies: first review and preserve/commit the existing Wave 2.1 i18n
  working tree. No product dependency remains. The OPS reboot/device checks may
  run independently but should be completed before relying on unattended
  production recovery.

## Suggested Next 5 Tasks

1. **A11Y-02 — Correct light-theme contrast.**
2. **A11Y-03/A11Y-04 — Standardize accessible dialogs and forms.**
3. **UX-01 — Unblock clean-install catalog onboarding.**
4. **UX-02/UX-03 — Improve mobile context and route recovery.**
5. **FUN-02 — Correct Inventory loading count.**

Do not promote SEC-01 ahead of these tasks unless the application moves to
public Internet exposure, an untrusted network, or multiple untrusted users.
