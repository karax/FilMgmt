# P0/P1 Audit Closure and Wave 1 Readiness

Date: 2026-09-03

Scope: challenge review of the audit Executive Summary, P0/P1 findings and
Recommended Execution Plan. This is not a new full-system audit.

## Decision summary

| Finding | Original | Decision | Evidence and rationale |
| --- | --- | --- | --- |
| REL-01 source reproducibility | P0 | P0 defect no longer reproduces; keep a P0 release gate until the clean-host run is complete | Before this closure document was created, the branch had zero untracked paths. Commit `4370ec9` added 107 paths, including the previously missing runtime, migration, test, tooling and documentation files. A `git archive HEAD` contained all 306 tracked files and all seven representative sentinels checked. Dependency installation and the complete gate were not rerun from that archive. |
| FUN-01 Print Job save failures | P1 | **Keep P1** | `NewPrintJobPage` and `EditPrintJobPage` pass mutation errors as `submitError`, but `PrintJobForm` does not destructure or render that prop. A rejected create/edit therefore leaves the user on the form without server or network feedback. This is a reproduced code path in a core mutation. |
| SEC-01 application authentication | P1 | **Reclassify to P2 for the supported private deployment; P0 exposure gate for an Internet-public service** | The API has no authentication dependency and exposes reads, writes, uploads and permanent delete. That is real. Its likelihood was overstated for one administrator on a trusted LAN/Tailnet, where the network is the current identity boundary. It must not be exposed to the public Internet in this state. |
| I18N-01/A11Y-01 language behavior | P1 | **Reclassify to P2; keep consolidated** | The finding is concrete: the document starts with `lang="en"`, language changes only update local storage, and core Print/Spool copy remains hard-coded. This impairs localization and assistive technology but does not threaten data or availability in the stated deployment. Both symptoms share the locale-integration boundary and can use one acceptance suite. |
| A11Y-02 light-theme contrast | P1 | **Reclassify to P2** | The light accent `#00a6a6` is reused for small text and focus indicators. Measured contrast is 3.00:1 on white, 2.74:1 on the canvas and 2.86:1 on the raised surface, below 4.5:1 for normal text and below 3:1 on two common surfaces for non-text focus. The impact is real accessibility debt, not a release/safety failure for this beta. It remains separate from language behavior because the cause and validation method differ. |
| STO-01 G-code storage lifecycle | P1 | **Keep P1** | Uploads have a per-file 100 MiB default, but no aggregate quota, TTL or callable cleanup endpoint/job. `delete_upload()` exists only as an unreferenced service method. Repeated uploads can exhaust Raspberry Pi storage and affect both availability and SQLite safety. |
| OPS-01 production operations | P1 | **Keep P1, narrow to the minimum supported topology** | There is no tracked production service/reverse-proxy configuration, startup procedure, or coordinated database/upload backup and restore procedure. On a self-hosted Pi this is a direct availability and recoverability risk. Advanced multi-host operations are out of scope. |
| UX-01 clean-install catalog onboarding | P1 | **Reclassify to P2** | Empty catalogs disable Spool creation and tell the user to create records, while the UI has no catalog management route. Seed commands provide a viable administrator path, so this is a browser-only onboarding defect rather than a release blocker for a technically supervised deployment. |
| DOC-01 root README | P1 | **Merge into OPS-01** | The README still claims removed Location support and missing current flows and uses development startup guidance. This evidence is concrete, but a second P1 duplicates the release/runbook deliverable. README accuracy is now an OPS-01 acceptance item. |

No reviewed item was underestimated in the stated private deployment. SEC-01
does become an absolute blocker if public exposure is introduced.

## Consolidated causes and dependencies

- **Release delivery:** REL-01 is a gate for every later change. It does not
  share an implementation fix with the product findings.
- **Core form recovery:** FUN-01 is independent and can be implemented after
  the repository gate.
- **Storage safety:** STO-01 is independent in code, but its chosen quota,
  retention and backup behavior must be documented by OPS-01.
- **Deployment trust boundary:** OPS-01 must state the supported bind address,
  reverse proxy/Tailscale boundary and public-exposure prohibition before
  SEC-01 can be specified without guessing.
- **Release documentation:** DOC-01 is absorbed by OPS-01; maintaining two
  findings would duplicate commands, topology and acceptance checks.
- **Frontend quality:** I18N-01/A11Y-01 stays consolidated. A11Y-02 remains
  separate because token contrast is not caused by locale integration.
- **Onboarding:** UX-01 depends on the supported clean-install procedure in
  OPS-01 but is not required when administrator-run seeds are the declared
  beta contract.

## Threat model for the real deployment

### Trusted actors

- the Raspberry Pi administrator with shell and filesystem access;
- the intended operator using the inventory and Print Tracker;
- explicitly trusted Tailscale users/devices when Tailnet access is enabled.

Other devices on a shared LAN, guests, IoT devices, exit-node users and
subnet-routed peers are not automatically trusted merely because they are not
on the public Internet.

### Network boundaries

1. The application process and SQLite/upload files on the Pi are the primary
   data boundary.
2. Loopback or a same-host reverse proxy is the strongest current application
   boundary.
3. A private LAN is only a trusted boundary when its membership and Wi-Fi are
   controlled.
4. Tailscale supplies device/user network admission, but the application
   cannot distinguish authorized roles once a peer can reach the API.
5. A public DNS name does not itself change the boundary. Public ingress does;
   a domain reachable only through Tailscale remains a private deployment.

CORS is a browser policy, not authentication. Direct HTTP clients can call the
API regardless of the configured browser origins.

### Likely threats now

- accidental or unauthorized mutation/deletion by another reachable trusted
  peer;
- a compromised LAN or Tailnet device calling catalog, Print, Spool or upload
  endpoints;
- storage exhaustion through repeated valid G-code uploads;
- loss or corruption after power/media failure without coordinated backup;
- disclosure of inventory/print metadata, whose confidentiality impact is
  lower than the integrity and availability impact in this product.

For a single operator with the API bound to loopback or reachable only through
a tightly controlled Tailnet, application authentication is P2 defense in
depth. For an untrusted LAN, broad shared Tailnet, or multi-user deployment it
returns to P1. Public Internet exposure of the current unauthenticated API is
prohibited and authentication/authorization becomes a P0 precondition. No
authentication implementation is part of this closure.

## REL-01 current-state audit

Commands used against the current branch:

```text
git status --porcelain=v2 --untracked-files=all  -> 0 entries before edits
git ls-files --others --exclude-standard         -> 0 entries before edits
git diff-tree --diff-filter=A HEAD               -> 107 paths in 4370ec9
git ls-tree -r HEAD                              -> 306 tracked files
git archive HEAD                                 -> 306 files
required sentinels present in archive            -> 7/7
final untracked list after documentation edits   -> p0-p1-closure.md only
```

The audit's “approximately 55” figure is not an exact path count that can be
reproduced from Git history. The fixing commit added 107 individual paths. The
likely discrepancy is directory-collapsed status output or a subset that
excluded documentation/static outputs. There were no pre-existing actionable
untracked paths. This review itself creates one new documentation path:
`docs/audits/p0-p1-closure.md`; it is **MUST COMMIT** after maintainer review.
It is not generated and must not be ignored. No commit is performed here.

### Retrospective classification of the 107 added paths

These rules are exhaustive and mutually exclusive for the paths added by
`4370ec9`:

| Classification | Exact path set | Count | Disposition |
| --- | --- | ---: | --- |
| Source code | `backend/app/api/gcode_uploads.py`; `backend/app/config.py`; all five `backend/app/schemas/gcode_*.py`; all five `backend/app/services/gcode_*.py`; `frontend/playwright.e2e.config.ts`; the seven `frontend/scripts/*.mjs`; non-test G-code/QR/print-cost files under `frontend/src/api`, `components/spool`, `hooks`, `lib`, `pages` and `types`; `frontend/src/config/manual.json` | 36 | **MUST COMMIT** |
| Tests | Five `backend/tests/test_gcode_*.py`; `frontend/e2e/smoke.spec.ts`; and the eleven added `*.test.ts`/`*.test.tsx` frontend files | 17 | **MUST COMMIT** |
| Migration | `backend/alembic/versions/f2a8c7d190b4_remove_storage_add_store_name.py` | 1 | **MUST COMMIT** |
| Documentation | The two audit Markdown files; `docs/gcode.md`; `docs/headless-browser-testing.md`; `docs/qr-format.md`; and four non-image files under `docs/user-guide/` | 9 | **MUST COMMIT** |
| Static product asset | The 41 PNGs under `docs/user-guide/images/` and `frontend/public/favicon.svg` | 42 | **MUST COMMIT** for the current documentation/product packaging. The screenshots are **REGENERATABLE**, but must not be ignored unless the docs pipeline generates them before use. |
| Generated-but-required artifact | The two user-guide PDFs under `frontend/public/docs/` | 2 | **MUST COMMIT** under the current build, because the product links to them. They are **REGENERATABLE** and may move to release generation only after the build enforces that dependency. |
| Runtime/local artifact | None in the fixing commit and none currently untracked | 0 | Databases, upload contents, virtual environments, `node_modules`, build output, test reports, logs and local agent/editor state are **MUST IGNORE**. Current ignore rules cover these classes. |
| **Total** |  | **107** |  |

Representative tracked/archive sentinels were the G-code API, current Alembic
head, G-code and QR pages, browser smoke test, source user guide and shipped
user-guide PDF. This proves the omission symptom is gone without claiming that
dependency installation from scratch has been exercised.

## Exact P0 closure checklist

- [x] At review start, `git ls-files --others --exclude-standard` returned no
  pre-existing product path.
- [x] At review start, `git status --porcelain=v2 --untracked-files=all`
  returned no path.
- [ ] After accepting this review, add
  `docs/audits/p0-p1-closure.md` to the intended commit. It is the only final
  untracked path and is **MUST COMMIT**; do not ignore it.
- [x] Runtime, migration, test, tooling, documentation and shipped-asset
  sentinels are present in `HEAD` and in `git archive HEAD`.
- [x] The archive file count matches the `HEAD` file count: 306/306.
- [ ] On a clean host/directory, extract `git archive HEAD`; do not copy the
  repository virtual environment, `node_modules`, database, uploads or build
  output.
- [ ] Install backend production and development dependencies only from the
  tracked requirement files.
- [ ] Point `DATABASE_URL` to a new temporary SQLite file, run `alembic upgrade
  head`, and run the migration drift check.
- [ ] Run backend tests and confirm the known baseline: **443 passed**.
- [ ] Run `npm ci`, frontend tests and typecheck; confirm **274 passed** and
  **typecheck passed**.
- [ ] Run the production frontend build, Python compilation and the eight
  Chromium smoke scenarios used by the audit.
- [ ] Start the built topology and smoke health, one read, one reversible
  mutation and G-code upload/analysis using only files from the archive.
- [ ] Confirm generated/runtime output is ignored and that no required product
  path appears as untracked after the gate.

REL-01 may be marked fully closed when all unchecked items pass. No Git commit
is requested or performed by this checklist.

## Known audit baseline

Recorded, not rerun during this challenge review:

- Backend tests: **443 passed**
- Frontend tests: **274 passed**
- Typecheck: **passed**

## Implementation-ready Wave 1

1. **REL-01 clean-host gate** — execute the unchecked checklist above. This is
   verification, not a product-code change.
2. **FUN-01 visible Print save failures** — render localized 409, 422 and
   network errors; preserve values; prevent duplicate submit; focus associated
   feedback; add create/edit component tests.
3. **STO-01 bounded upload lifecycle** — decide explicit defaults first, then
   implement aggregate quota, TTL/manual cleanup, complete sidecar cleanup,
   disk-full feedback and concurrency/path-safety tests.
4. **OPS-01 minimum Pi runbook plus README** — declare one supported private
   topology, bind/exposure rules, non-reload service, frontend/reverse-proxy
   behavior, startup/health, upgrade/rollback and coordinated SQLite/upload
   backup/restore. State that public ingress is unsupported without auth.

Wave 1 dependencies: REL-01 precedes all implementation; FUN-01 and STO-01 can
then proceed independently; OPS-01 consumes the final storage policy and
records the trust boundary. SEC-01, localization, contrast and onboarding move
to Wave 2 for the supported private beta. Any decision to enable public ingress
moves SEC-01 ahead of release as a P0 gate.

Wave 1 exit criteria:

- the clean-host gate passes without borrowing product files;
- Print create/edit failures are visible and recoverable;
- upload storage cannot grow without an explicit bound and cleanup path;
- a Pi administrator can install, start, upgrade, back up and restore the
  supported private deployment from tracked documentation;
- public ingress remains disabled unless authentication and authorization are
  implemented and tested.
