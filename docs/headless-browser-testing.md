# Chromium Headless + Playwright

The project validates browser behavior with the system Chromium and Playwright.
This is intentionally independent of Codex's integrated browser runtime:
`agent.browsers.list()` may remain empty and is not a tooling failure.

## Requirement

Install one system Chromium suitable for the host architecture. On the current
Raspberry Pi target that is Debian ARM64 and the executable is normally
`/usr/bin/chromium`. Do not run `playwright install`; this project does not
download Playwright-managed browsers.

Executable discovery uses this order:

1. `CHROMIUM_PATH`, when explicitly set;
2. `chromium`;
3. `chromium-browser`;
4. `google-chrome`;
5. `google-chrome-stable`.

For example:

```bash
CHROMIUM_PATH=/custom/path/chromium npm run browser:smoke
```

The normal configuration does not add `--no-sandbox`. Keep Chromium's own
sandbox enabled. In the current Codex executor, Chromium can fail before launch
because the executor restricts Crashpad socket setup; run the browser command
outside that executor isolation when necessary. This is a Codex execution
limitation, not an ARM64 Chromium incompatibility and not a reason to change
the project's default Chromium flags.

## Commands

From `frontend/`:

```bash
npm run browser:doctor
npm run browser:smoke
npm run test:e2e
npm run browser:screenshot -- /gcode
```

`browser:doctor` reports architecture, Chromium path/version, Node,
Playwright, and reachability of the local frontend/backend. Its nonzero exit
codes distinguish Chromium (2), frontend (3), backend (4), and both servers
(5).

`browser:smoke` and `test:e2e` run the same focused Playwright suite. It uses
system Chromium, headless mode, one worker, no video, screenshots only on
failure, and traces retained on failure.

`browser:screenshot` captures both desktop (1440x900) and mobile (390x844)
versions of a local route. It accepts only a local path beginning with `/` and
sanitizes the output name. For `/gcode`, the files are:

```text
artifacts/browser/gcode-desktop.png
artifacts/browser/gcode-mobile.png
```

## Local servers

E2E uses `http://127.0.0.1:5173`. The Playwright configuration reuses a Vite
server already running on that port. If it is absent, Playwright starts a local
Vite process on `127.0.0.1:5173` and cleans up only that process afterward.

The backend remains a separate local prerequisite at
`http://127.0.0.1:8000`. The runner never kills user-owned backend or Vite
processes. Check both prerequisites with `browser:doctor` before a smoke run.

The normal Vite development configuration still supports LAN/Tailscale use;
this tooling does not change Tailscale, firewall, DNS, or runtime host settings.

## Smoke coverage

The initial suite uses semantic assertions and real local requests for:

- `/` redirected to Inventory, including the table view;
- `/gcode` and its accessible file input;
- `/scan` and its manual spool-code fallback without a webcam;
- `/spools/:code` using the first code dynamically returned by `/api/spools`
  when the inventory is not empty;
- `/`, `/gcode`, and `/scan` at 390x844 without horizontal overflow.

It fails on uncaught `pageerror`, `console.error`, failed local API requests,
or local API responses with HTTP 500 or higher. `console.warn` remains visible
but is not treated as an error automatically. The browser's explicit
`net::ERR_ABORTED` cancellation during page navigation/teardown is not a
network failure; actual failed API requests remain errors.

## Artifacts

Failure output is stored under `test-results/` and `playwright-report/`; manual
screenshots live in `artifacts/browser/`. All of these locations are ignored by
Git.

## Troubleshooting

- **Chromium not found:** install the distribution's Chromium package or set
  `CHROMIUM_PATH` to an executable file, then run `browser:doctor` again.
- **Frontend unavailable:** run `npm run dev -- --host 127.0.0.1 --port 5173`,
  or let the Playwright `webServer` start it when no process owns the port.
- **Backend unavailable:** start the project's Uvicorn environment on
  `127.0.0.1:8000`; the browser runner intentionally does not expose it on the
  network.
- **Port 5173 occupied:** reuse the existing correct Vite server, or stop only
  the process you own before using the automatic local server.
- **Codex executor Crashpad/sandbox error:** run the same CLI command outside
  that executor isolation. Do not make `--no-sandbox` a global default.
- **Wrong executable:** `CHROMIUM_PATH=/path/to/chromium npm run browser:doctor`
  confirms the selected binary and version before the test runs.
