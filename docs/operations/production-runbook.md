# Filament Command Center — Production Runbook

## 1. Purpose and scope

This is the canonical operator guide for one private, single-user Filament
Command Center installation on a Raspberry Pi 4 (ARM64, about 2 GB RAM). It
covers production setup, services, access, health, backup, restore, update,
rollback, and recovery. Development still uses Uvicorn reload and Vite as
described in the root README; neither development server is used in production.

Authentication is not implemented. **Do not expose Filament Command Center
directly to the public Internet.** Public port forwarding, Tailscale Funnel, and
an Internet-facing reverse proxy are unsupported.

## 2. Supported deployment model

- Recommended remote profile: private Tailnet access through Tailscale Serve
  with Tailnet HTTPS and Tailnet access controls.
- Trusted LAN profile: HTTP on TCP port 8080. HTTP is not HTTPS; camera access
  and other browser secure-context features may be unavailable.
- Public Internet profile: **NOT SUPPORTED** until authentication and
  authorization exist.

The application runs as the login user, never as root. Root is needed only for
explicit OS package installation and enabling user-service linger.

## 3. Production architecture

```text
Browser on trusted LAN or Tailnet
  -> Tailscale HTTPS (recommended remotely) or trusted-LAN HTTP :8080
  -> Caddy :8080
       -> static frontend/dist (only public file root)
       -> /api and /api/* -> FastAPI 127.0.0.1:8000
  -> SQLite database and local G-code storage
```

Caddy handles `/api` before the SPA fallback. Unknown frontend routes fall back
to `index.html`; unknown API routes remain FastAPI JSON 404 responses. The
repository, database, backups, environment file, and G-code storage are outside
the configured static root and cannot be downloaded through Caddy.

## 4. Requirements

- 64-bit Raspberry Pi OS or comparable systemd-based Debian/Raspbian
- Python 3.11 or newer, `venv`, Git, and build tools
- Node.js 24.x, npm 11 or newer
- Caddy 2
- Tailscale when using the recommended remote profile

Check first:

```bash
python3 --version
node --version
npm --version
git --version
command -v caddy
command -v tailscale
```

If the base tools are absent, install them deliberately:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip build-essential curl
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
```

For Caddy on Debian/Raspbian, use its official stable package repository:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
sudo chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
sudo systemctl disable --now caddy
```

The packaged system Caddy service is disabled because this deployment uses the
tracked non-root user service on port 8080. See the
[official Caddy installation guide](https://caddyserver.com/docs/install) if
the distribution changes.

## 5. Initial production setup

The tracked units intentionally use one standard, non-personal path. Define the
same variables for every command in this runbook:

```bash
FCC_HOME="$HOME/.local/share/filament-command-center/app"
FCC_CONFIG="$HOME/.config/filament-command-center"
FCC_USER_UNITS="$HOME/.config/systemd/user"
```

Clone the production checkout and apply a restrictive default file mask:

```bash
umask 077
install -d -m 700 "$(dirname "$FCC_HOME")" "$FCC_CONFIG" "$FCC_USER_UNITS"
git clone git@github.com:karax/FilMgmt.git "$FCC_HOME"
cd "$FCC_HOME"
```

Create the backend environment, initialize the schema, and seed the first-run
catalogs:

```bash
cd "$FCC_HOME/backend"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/python -m app.scripts.seed_manufacturers
.venv/bin/python -m app.scripts.seed_materials
install -d -m 700 "$FCC_HOME/data/uploads/gcode" "$FCC_HOME/backups"
```

Install frontend dependencies and build the production assets:

```bash
cd "$FCC_HOME/frontend"
npm ci
npm run build
test -f dist/index.html
test -f dist/docs/filament-command-center-user-guide.pdf
```

Install the versioned configuration and user units:

```bash
install -m 600 "$FCC_HOME/deploy/env/production.env.example" "$FCC_CONFIG/env"
install -m 600 "$FCC_HOME/deploy/proxy/Caddyfile" "$FCC_CONFIG/Caddyfile"
install -m 644 "$FCC_HOME"/deploy/systemd/* "$FCC_USER_UNITS/"
systemctl --user daemon-reload
systemctl --user enable --now filament-command-center.service
systemctl --user enable --now filament-command-center-web.service
systemctl --user enable --now filament-command-center-backup.timer
sudo loginctl enable-linger "$USER"
```

Linger allows the user services to start at boot without an interactive login.
Do not run the application services with `sudo`.

## 6. Configuration

Production reads:

```text
~/.config/filament-command-center/env
```

The tracked example is `deploy/env/production.env.example`. Keep the installed
file mode `0600`; do not commit the installed file. Reload configuration with a
service restart. Actual supported fields and defaults are:

| Field | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | SQLite at `data/filament.db` | SQLAlchemy database URL; operations require a file-backed SQLite URL. |
| `GCODE_UPLOAD_DIRECTORY` | `data/uploads/gcode` | Managed upload directory. |
| `GCODE_MAX_UPLOAD_BYTES` | `104857600` | Maximum bytes per upload (100 MiB). |
| `GCODE_UPLOAD_RETENTION_DAYS` | `30` | Upload age before cleanup eligibility. |
| `GCODE_UPLOAD_MAX_TOTAL_BYTES` | `2147483648` | Managed storage quota (2 GiB). |
| `GCODE_UPLOAD_TEMP_STALE_SECONDS` | `3600` | Abandoned temp-file age. |
| `GCODE_UPLOAD_CLEANUP_ENABLED` | `true` | Cleanup before a new upload. |
| `GCODE_UPLOAD_RETENTION_ENABLED` | `true` | Age-based expiry. |
| `FCC_BACKUP_DIRECTORY` | `backups/` | Operations-only verified-backup directory. |
| `FCC_BACKEND_HEALTH_URL` | `http://127.0.0.1:8000/api/health` | Quick-check backend URL. |
| `FCC_FRONTEND_URL` | `http://127.0.0.1:8080/` | Quick-check frontend URL. |

Numeric validation and accepted boolean spellings are documented in
`docs/gcode.md`. Absolute custom data paths must be owned by the service user.
Recommended permissions are environment `0600`, database and backup files
`0600`, and data, backup, and G-code directories `0700`. Never use `chmod 777`.

When running maintenance manually, load the same environment:

```bash
set -a
. "$FCC_CONFIG/env"
set +a
```

## 7. Building the frontend

Production always serves `frontend/dist` built by:

```bash
cd "$FCC_HOME/frontend"
npm ci
npm run build
```

`npm run dev` and `vite preview` are not production servers. The build copies
the manual to
`frontend/dist/docs/filament-command-center-user-guide.pdf`; Caddy serves it at
`/docs/filament-command-center-user-guide.pdf`.

## 8. Services

The real user service names are `filament-command-center.service` (FastAPI),
`filament-command-center-web.service` (Caddy), and the optional daily
`filament-command-center-backup.timer`. Journald captures standard output and
errors. The API has `Restart=on-failure` and `RestartSec=5s`.

### Start

```bash
systemctl --user start filament-command-center.service filament-command-center-web.service
```

### Stop

```bash
systemctl --user stop filament-command-center-web.service filament-command-center.service
```

### Restart

```bash
systemctl --user restart filament-command-center.service filament-command-center-web.service
```

### Status

```bash
systemctl --user status filament-command-center.service filament-command-center-web.service
systemctl --user status filament-command-center-backup.timer
```

### Enable at boot

```bash
systemctl --user enable filament-command-center.service filament-command-center-web.service
sudo loginctl enable-linger "$USER"
```

Disable boot startup without deleting data:

```bash
systemctl --user disable filament-command-center-web.service filament-command-center.service
```

## 9. Logs

Recent application and web logs:

```bash
journalctl --user -u filament-command-center.service -u filament-command-center-web.service -n 100 --no-pager
```

Live follow:

```bash
journalctl --user -u filament-command-center.service -u filament-command-center-web.service -f
```

Current boot only:

```bash
journalctl --user -b -u filament-command-center.service -u filament-command-center-web.service --no-pager
```

Backup failures:

```bash
systemctl --user status filament-command-center-backup.service
journalctl --user -u filament-command-center-backup.service -n 100 --no-pager
```

## 10. Network access

### Trusted LAN

The LAN entrypoint is `http://<raspberry-hostname-or-LAN-address>:8080`. Discover
the real values instead of placing an address in configuration:

```bash
hostname
hostname -I
```

Limit access to a trusted network and do not create router port forwarding.
HTTP traffic is not TLS-protected. Browsers normally require HTTPS for camera
APIs, so the scanner may require the Tailscale profile.

### Tailscale / HTTPS

Tailscale Serve is the recommended remote profile. Confirm this Pi is connected,
then proxy the already-running Caddy entrypoint in persistent background mode:

```bash
tailscale status
tailscale serve --bg 127.0.0.1:8080
tailscale serve status
```

The commands print the actual `https://...ts.net` address; do not hardcode it.
Serve requires MagicDNS and Tailnet HTTPS certificates and may present a one-time
administrator consent link. Tailnet ACLs still apply. Background Serve resumes
after Tailscale or device restart. See the
[official Tailscale Serve guide](https://tailscale.com/docs/features/tailscale-serve).

Do not use `tailscale funnel`: Funnel is public Internet exposure.

### Public Internet

**NOT SUPPORTED. Do not expose Filament Command Center directly to the public
Internet while authentication is not implemented.** This includes public DNS
reverse proxies, router port forwarding, and Tailscale Funnel.

## 11. Health checks

Quick operational check (lightweight `SELECT 1`, not full DB integrity):

```bash
cd "$FCC_HOME/backend"
.venv/bin/python -m app.scripts.check_health
```

A healthy command exits 0 and prints:

```text
Backend: OK (...)
Frontend: OK (...)
Database: OK (...)
G-code storage: OK (...)

Overall: HEALTHY
```

Any failed component produces `Overall: UNHEALTHY` and a non-zero exit code.
Direct probes are:

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/api/health
curl --fail --silent --show-error http://127.0.0.1:8080/ > /dev/null
```

Run the deeper, slower SQLite maintenance check only during maintenance or when
behavior is abnormal:

```bash
cd "$FCC_HOME/backend"
.venv/bin/python -m app.scripts.check_database
```

## 12. G-code storage maintenance

G-code cleanup already runs before uploads when enabled. There is no redundant
timer. Inspect without deleting, then run the same STO-01 cleanup service:

```bash
cd "$FCC_HOME/backend"
.venv/bin/python -m app.scripts.cleanup_gcode_uploads --dry-run
.venv/bin/python -m app.scripts.cleanup_gcode_uploads
```

G-code files are bounded analysis inputs and caches, not canonical inventory or
print history. Core database backups therefore **exclude** G-code storage. If a
particular source file must be retained historically, keep the original outside
the managed upload directory. As an optional point-in-time archive, stop the API
and archive the directory separately:

```bash
systemctl --user stop filament-command-center.service
tar -C "$FCC_HOME/data/uploads" -czf "$FCC_HOME/backups/gcode-$(date -u +%Y-%m-%dT%H%M%SZ).tar.gz" gcode
systemctl --user start filament-command-center.service
```

## 13. Database backup

The SQLite database is canonical: manufacturers, materials, spools, weight
history, print jobs, and their spool associations are included. Code, generated
frontend files, logs, G-code uploads, and caches are excluded.

Create an online, transactionally consistent backup while the API is running:

```bash
cd "$FCC_HOME/backend"
.venv/bin/python -m app.scripts.backup_database
```

The command uses Python's SQLite backup API, never raw `cp` of an active DB. It
writes a UTC-named `.sqlite` file and adjacent `.manifest.json` in `backups/`,
with mode `0600`. The manifest records creation time, size, SHA-256, Git
revision, Alembic revision, and verification results. A failed verification
returns non-zero and is not reported as success.

Daily verified backup is optional and independent of application startup:

```bash
systemctl --user enable --now filament-command-center-backup.timer
systemctl --user list-timers filament-command-center-backup.timer
```

There is intentionally no automatic deletion. Review backups before removing
old pairs:

```bash
find "$FCC_HOME/backups" -maxdepth 1 -type f -mtime +30 -print
```

A backup on the same microSD helps with logical errors or accidental deletion,
but **does not protect against microSD failure, Pi loss, or device/filesystem
loss**. Periodically copy verified `.sqlite` and `.manifest.json` pairs to
another computer, NAS, or external drive.

## 14. Backup verification

Every backup command already runs `PRAGMA integrity_check`,
`PRAGMA foreign_key_check`, and manifest checksum verification. Recheck a copied
backup by passing its path:

```bash
cd "$FCC_HOME/backend"
.venv/bin/python -m app.scripts.check_database --database "$FCC_HOME/backups/filament-command-center-YYYY-MM-DDTHHMMSSZ.sqlite"
```

`YYYY-MM-DDTHHMMSSZ` is an operator-replaced filename placeholder. Success means
`integrity_check: ok`, zero foreign-key violations, and a matching adjacent
manifest checksum.

## 15. Database restore

Never replace a database while FastAPI may write. First identify a verified
backup and stop the backend:

```bash
systemctl --user stop filament-command-center.service
systemctl --user is-active filament-command-center.service
```

The second command must report `inactive`. Restore requires two explicit flags:

```bash
cd "$FCC_HOME/backend"
.venv/bin/python -m app.scripts.restore_database \
  "$FCC_HOME/backups/filament-command-center-YYYY-MM-DDTHHMMSSZ.sqlite" \
  --replace \
  --confirm-backend-stopped
```

Before replacement, the tool validates SQLite format, manifest filename/size,
SHA-256, integrity, foreign keys, and compatibility with this checkout's Alembic
head. It creates a verified `pre-restore-<UTC>.sqlite` safety backup, copies to a
temporary file, verifies it, and atomically replaces the target. It never starts
the backend automatically:

```bash
systemctl --user start filament-command-center.service
cd "$FCC_HOME/backend"
.venv/bin/python -m app.scripts.check_health
```

`--allow-schema-mismatch` exists only for expert disaster recovery paired with
the matching historical code revision; do not use it for a normal restore.

## 16. Updating

Deploy only a named branch, tag, or commit. The helper refuses any dirty working
tree and never runs `git reset --hard`:

```bash
cd "$FCC_HOME/backend"
.venv/bin/python -m app.scripts.update_production <target-tag-branch-or-commit>
```

The angle-bracket value is an operator-replaced explicit target. The helper:

1. checks the current application health, clean Git status, current revision,
   and free disk space;
2. creates and verifies an online database backup;
3. fetches refs and resolves the explicit target to a commit;
4. records old revision, target revision, backup, checksum, and schema revision;
5. requires a fast-forward merge;
6. installs Python requirements and runs `npm ci` plus `npm run build`;
7. runs `alembic upgrade head`;
8. restarts both services and runs the quick health check.

Preview local revision safety without updating or networking:

```bash
cd "$FCC_HOME/backend"
.venv/bin/python -m app.scripts.update_production --preflight-only HEAD
```

If a step fails, the helper stops, reports failure, and never performs an
automatic destructive rollback. Read the recorded `update-<UTC>.json`, inspect
service logs, and choose the appropriate rollback below.

## 17. Rollback

Act promptly and record the current state. Never use a blind `alembic downgrade`:
some migrations cannot preserve newer data.

**Case A — no database migration was applied:** stop services, move the checkout
to the `previous_revision` recorded by the update, install that revision's
dependencies, rebuild, restart, and check health:

```bash
systemctl --user stop filament-command-center-web.service filament-command-center.service
cd "$FCC_HOME"
git status --porcelain
git switch --detach <previous-revision>
cd backend
.venv/bin/python -m pip install -r requirements.txt
cd ../frontend
npm ci
npm run build
systemctl --user start filament-command-center.service filament-command-center-web.service
cd ../backend
.venv/bin/python -m app.scripts.check_health
```

`<previous-revision>` is replaced with the recorded commit. Stop if Git status
is not empty; preserve local changes rather than resetting them.

**Case B — migration was applied:** use the matching previous code revision and
restore the verified pre-update DB backup with the Section 15 procedure. Do not
assume an Alembic downgrade is safe. Restoring the pre-update database discards
records created after that backup, so decide quickly and communicate the data
window before restoring.

## 18. Recovery after power loss

Power loss alone does not prove SQLite corruption. Do not restore automatically.

1. Confirm the Pi booted: `uptime`.
2. Check both services with `systemctl --user status` commands from Section 8.
3. Check the frontend: `curl -I http://127.0.0.1:8080/`.
4. Check `curl http://127.0.0.1:8000/api/health`.
5. Inspect current-boot logs using Section 9.
6. Check filesystem free space with `df -h "$FCC_HOME"`.
7. If behavior is abnormal, run `app.scripts.check_database`.
8. Confirm its `foreign_key_check` reports zero violations.
9. Run G-code cleanup `--dry-run` and inspect storage availability.
10. Restore a verified backup only when actual database damage is confirmed.

After installation, one physical reboot and automatic-return check is required
as manual validation. Do not reboot during an update or backup.

## 19. Disk/storage troubleshooting

```bash
df -h "$FCC_HOME"
du -sh "$FCC_HOME/data" "$FCC_HOME/data/uploads/gcode" "$FCC_HOME/backups"
stat --format='%n %s bytes' "$FCC_HOME/data/filament.db"
find "$FCC_HOME/backups" -maxdepth 1 -type f -printf '%TY-%Tm-%Td %10s %f\n' | sort
```

If space is low, inspect the G-code dry-run first, copy verified backups off the
microSD, and manually remove only reviewed old backup/manifest pairs. Do not
delete the live DB, its SQLite sidecars, or files from an active upload.

## 20. Common failures

- **Backend inactive:** inspect its current-boot journal; verify `.venv`, env
  syntax, data-directory ownership, and migration state.
- **Caddy inactive:** confirm `/usr/bin/caddy` exists, validate the Caddyfile,
  and ensure port 8080 is free: `ss -ltnp | grep ':8080'`.
- **Frontend shows 404:** rebuild `frontend/dist` and confirm `index.html`.
- **API returns HTML:** the deployed Caddyfile is wrong; reinstall the tracked
  config so the `/api` handler precedes SPA fallback.
- **Manual PDF missing:** run `npm run build`; the build fails if the source PDF
  is absent or invalid.
- **Database locked:** wait for the current request to finish; do not kill power
  or copy the live DB. Inspect logs before restart.
- **Backup fails:** keep the last verified backup, inspect backup-service logs,
  permissions, free space, integrity, and the configured DB path.
- **Tailscale URL unavailable:** check `tailscale status` and
  `tailscale serve status`; confirm Tailnet HTTPS/MagicDNS and ACL permissions.

Validate production routing after changes:

```bash
curl --fail http://127.0.0.1:8080/ > /dev/null
curl --fail http://127.0.0.1:8080/settings > /dev/null
curl --fail http://127.0.0.1:8080/docs/filament-command-center-user-guide.pdf > /dev/null
curl --fail http://127.0.0.1:8080/api/health
curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' http://127.0.0.1:8080/api/not-found
```

The final command must print `404`, not `200`.

For a production-like Chromium smoke against already-running Caddy and FastAPI
(it does not start Vite), run:

```bash
cd "$FCC_HOME/frontend"
npm run test:e2e:production
```

## 21. Disaster recovery quick reference

1. Keep the damaged microSD/device unchanged when possible.
2. Prepare a clean matching code revision under the standard `FCC_HOME`.
3. Install dependencies and build the frontend using Sections 5–7.
4. Place a copied `.sqlite` plus matching `.manifest.json` outside Git tracking.
5. Run `check_database --database <backup>`.
6. Stop the backend and run the guarded restore from Section 15.
7. Start services, run quick health, and inspect logs.
8. Verify inventory, weight history, print jobs, Settings, and manual download.
9. Configure Tailscale Serve again only if `tailscale serve status` is empty.

Never treat the same-device backup directory as disaster-resistant storage.
