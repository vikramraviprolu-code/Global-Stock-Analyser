# Installation Guide

EquityScope is a single-tenant, browser-local equity research dashboard.
This guide covers every supported install path. Pick the one that
matches your platform.

> **Quick pick:**
> - macOS — [native LaunchDaemon installer](#1-macos--native-launchdaemon)
> - Linux server — [systemd unit](#2-linux--systemd-unit)
> - Linux desktop / Windows / WSL — [Docker (GHCR)](#3-docker-ghcr-image)
> - Any platform with Python 3.9+ — [pip from clone](#4-pip-from-clone)

---

## Prerequisites (any platform)

- Python 3.9, 3.11, 3.12, or 3.13 (only required for paths #1, #2, #4).
- Git (for paths #1, #2, #4).
- ~150 MB disk for the install + Python deps.
- Internet access during install (to download dependencies).
- A modern browser: Chrome, Safari, Firefox, Edge, or Brave.

---

## 1. macOS — native LaunchDaemon

The richest experience: green-padlock TLS via `mkcert`, custom
hostname `https://Global-Stock-Analyser/Local`, gunicorn, autostart
at login.

### One-time install

```bash
git clone https://github.com/vikramraviprolu-code/Global-Stock-Analyser.git
cd Global-Stock-Analyser
sudo bash scripts/install_daemon.sh
```

The installer will:

1. Stage the project at `/usr/local/global-stock-analyser/`.
2. Create a pinned virtualenv with all dependencies.
3. Install the `mkcert` local CA into your System keychain.
4. Generate a TLS leaf cert signed by that CA.
5. Add `127.0.0.1 Global-Stock-Analyser` to `/etc/hosts`.
6. Drop a LaunchDaemon plist at
   `~/Library/LaunchAgents/com.equityscope.global.plist`.
7. Start the daemon and verify it serves over TLS.

### Open the app

```
https://Global-Stock-Analyser/Local
```

Should load with a green padlock — no "Advanced → Proceed" warning.

### Manage the service

```bash
# Stop
sudo launchctl unload ~/Library/LaunchAgents/com.equityscope.global.plist

# Start
sudo launchctl load ~/Library/LaunchAgents/com.equityscope.global.plist

# View logs
log show --predicate 'process CONTAINS "equityscope"' --last 1h
```

### Uninstall

```bash
sudo bash scripts/uninstall_daemon.sh
mkcert -uninstall   # optional — removes the local CA from the keychain
```

### Audit

`INSTALL_AUDIT.md` ships with a clean-machine reproducibility checklist
covering pre-flight, install, smoke tour, and uninstall. Run through
it on any fresh macOS host before reporting bugs.

---

## 2. Linux — systemd unit

For Linux servers and desktops with `systemd` (Ubuntu 20.04+, Debian
11+, Fedora 38+, Arch, RHEL 9+, etc.).

### One-time install

```bash
git clone https://github.com/vikramraviprolu-code/Global-Stock-Analyser.git
cd Global-Stock-Analyser
sudo bash scripts/install_systemd.sh
```

The installer will:

1. Stage the project at `/opt/equityscope/`.
2. Create a Python venv at `/opt/equityscope/venv/`.
3. Install runtime deps + `waitress` (cross-platform WSGI server).
4. Render `scripts/equityscope.service.template` with your username.
5. Drop the unit at `/etc/systemd/system/equityscope.service`.
6. `systemctl enable --now` the service.
7. Smoke-check `127.0.0.1:5050` is serving.

### Open the app

```
http://127.0.0.1:5050
```

> Plain HTTP because no `mkcert`-equivalent on Linux ships out of the
> box. For HTTPS, run behind a reverse proxy (nginx, Caddy) with a
> Let's Encrypt cert, or set up `mkcert` manually and pass
> `--tls-cert` / `--tls-key` to the `equityscope` CLI.

### Manage the service

```bash
sudo systemctl status equityscope
sudo systemctl stop equityscope
sudo systemctl restart equityscope
journalctl -u equityscope -f             # tail logs
journalctl -u equityscope --since "1h ago"
```

### Uninstall

```bash
sudo bash scripts/uninstall_systemd.sh
```

### Hardening

The unit ships with kernel-level hardening on by default:
`NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`,
`MemoryDenyWriteExecute`, `RestrictNamespaces`, etc. The service can
only write inside `/opt/equityscope`. Loopback-only by design — never
expose `0.0.0.0`.

---

## 3. Docker (GHCR image)

The fastest install on Linux, Windows (Docker Desktop / WSL2), and
macOS without root. Multi-arch (amd64 + arm64) image published from
the official CI on every tagged release.

### Pull + run (latest)

```bash
docker pull ghcr.io/vikramraviprolu-code/global-stock-analyser:latest
docker run -p 5050:5050 --rm \
  --name equityscope \
  ghcr.io/vikramraviprolu-code/global-stock-analyser:latest
```

### Pull + run (pinned)

```bash
docker pull ghcr.io/vikramraviprolu-code/global-stock-analyser:v1.1.0
docker run -p 5050:5050 -d \
  --name equityscope \
  --restart unless-stopped \
  ghcr.io/vikramraviprolu-code/global-stock-analyser:v1.1.0
```

### Open the app

```
http://127.0.0.1:5050
```

### TLS in Docker

The image runs gunicorn over plain HTTP. For green padlock TLS, run
behind a reverse proxy:

```yaml
# docker-compose.yml example
services:
  equityscope:
    image: ghcr.io/vikramraviprolu-code/global-stock-analyser:v1.1.0
    expose: ["5050"]
    restart: unless-stopped
  caddy:
    image: caddy:latest
    ports: ["443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on: [equityscope]
volumes:
  caddy_data:
```

```caddyfile
# Caddyfile
equityscope.local {
  reverse_proxy equityscope:5050
}
```

### Manage the container

```bash
docker logs -f equityscope          # tail logs
docker stop equityscope             # stop
docker start equityscope            # start
docker rm equityscope               # remove
```

### Build the image yourself

```bash
git clone https://github.com/vikramraviprolu-code/Global-Stock-Analyser.git
cd Global-Stock-Analyser
docker build -t equityscope:dev .
docker run -p 5050:5050 --rm equityscope:dev
```

---

## 4. pip from clone

For development or any environment with Python 3.9+ that doesn't
match paths #1-#3 (e.g. Windows native, NixOS, FreeBSD).

> **PyPI publish (`pip install global-stock-analyser`) is planned for
> v1.2.0** — the project is in flat layout and needs a package
> restructure first. Track the migration in
> [issue #1](https://github.com/vikramraviprolu-code/Global-Stock-Analyser/issues).

### Install

```bash
git clone https://github.com/vikramraviprolu-code/Global-Stock-Analyser.git
cd Global-Stock-Analyser
python3 -m venv venv
source venv/bin/activate                  # Windows: .\venv\Scripts\activate
pip install -e .                          # registers `equityscope` console script
```

### Run

```bash
equityscope                                # serves on http://127.0.0.1:5050
equityscope --port 8080
equityscope --host 0.0.0.0                 # bind LAN — see SECURITY.md first
equityscope --debug                        # Flask dev server with reloader
equityscope --version
equityscope --help
```

### TLS

```bash
# Generate a self-signed cert (any CN works for loopback)
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout key.pem -out cert.pem -subj "/CN=localhost"

equityscope --tls-cert cert.pem --tls-key key.pem --debug
# Open https://127.0.0.1:5050 — accept the self-signed warning
```

For green-padlock TLS, install `mkcert` and use
`scripts/gen_cert.sh` (macOS / Linux) or invoke `mkcert` manually on
Windows.

---

## Verifying the install

Whichever path you chose, the install is healthy when:

```bash
curl -fsS http://127.0.0.1:5050/api/settings/server-info | python3 -m json.tool
# or for path #1:
curl -fsS https://Global-Stock-Analyser/Local/api/settings/server-info | python3 -m json.tool
```

returns a JSON object with `"version": "1.1.0"` (or whichever tag you
pinned to).

The full health check is in `INSTALL_AUDIT.md` — run through every
checkbox on a clean machine before reporting installer bugs.

---

## Configuration

EquityScope reads runtime settings from environment variables (and CLI
flags on path #4). Override defaults via:

| Env var | Default | Used by | Notes |
| --- | --- | --- | --- |
| `URL_PREFIX` | `""` | All | Mount under a subpath, e.g. `/equityscope`. |
| `SSL_CERT` / `SSL_KEY` | unset | macOS daemon, Docker, CLI | Path to TLS cert + key. |
| `TRUSTED_HOSTS` | `Global-Stock-Analyser,127.0.0.1,localhost` | All | Comma-separated `Host:` allow-list. |
| `AUTO_SHUTDOWN` | `1` | macOS daemon, CLI | Set to `0` to disable browser-driven idle shutdown. |
| `IDLE_TIMEOUT` | `45` | All | Seconds of idle before auto-shutdown fires. |
| `LOG_LEVEL` | `INFO` | All | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

CLI flags on path #4 always win over env vars. See `equityscope --help`
for the current list.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Cannot connect to 127.0.0.1:5050` | Daemon / container not running | macOS: `sudo launchctl list \| grep equityscope`. Linux: `systemctl status equityscope`. Docker: `docker ps`. |
| Browser shows "Not Secure" warning | TLS cert not trusted | macOS: re-run installer (re-installs mkcert CA). Path #4: regenerate cert + re-add to keychain. Docker: use a reverse proxy with Let's Encrypt. |
| Daemon crashloops at boot | Python venv mismatch | macOS: `sudo bash scripts/uninstall_daemon.sh && sudo bash scripts/install_daemon.sh`. Linux: same with `_systemd.sh`. |
| Port 5050 already in use | Another local process | Pass `--port 8080` (path #4), edit the LaunchDaemon plist (path #1), edit the systemd unit (path #2), or `-p 8080:5050` (path #3). |
| `mkcert: command not found` | mkcert not installed | macOS: `brew install mkcert`. Linux: `apt install mkcert` or download from https://github.com/FiloSottile/mkcert/releases. |
| `404 on /Local` | Reverse proxy strips the prefix | Set `URL_PREFIX=/Local` env var when running the app. |
| Stale data after restart | In-memory cache wipes on restart by design | Re-run an analysis — caches re-fill from the providers. |
| `pytest: command not found` | Dev extras not installed | `pip install -e ".[dev]"` (path #4 only). |

For anything else, file an issue:
https://github.com/vikramraviprolu-code/Global-Stock-Analyser/issues

---

## Upgrading

| Path | Steps |
| --- | --- |
| **macOS daemon** | `cd Global-Stock-Analyser && git pull && sudo bash scripts/install_daemon.sh` (idempotent — safely re-runs over an existing install). |
| **Linux systemd** | `cd Global-Stock-Analyser && git pull && sudo bash scripts/install_systemd.sh`. |
| **Docker** | `docker pull ghcr.io/.../global-stock-analyser:vX.Y.Z && docker stop equityscope && docker rm equityscope && docker run -p 5050:5050 -d --name equityscope ghcr.io/.../global-stock-analyser:vX.Y.Z`. |
| **pip clone** | `git pull && pip install -e . --upgrade`. |

State is preserved across upgrades (lives in your browser's
localStorage, not on the server). The server caches are in-memory and
reset on every restart by design — see SECURITY.md.

---

## Uninstall

| Path | Steps |
| --- | --- |
| **macOS daemon** | `sudo bash scripts/uninstall_daemon.sh` + optional `mkcert -uninstall`. |
| **Linux systemd** | `sudo bash scripts/uninstall_systemd.sh`. |
| **Docker** | `docker stop equityscope && docker rm equityscope && docker rmi ghcr.io/.../global-stock-analyser`. |
| **pip clone** | `pip uninstall global-stock-analyser` + `rm -rf venv && rm -rf Global-Stock-Analyser`. |

To wipe browser-local state (watchlists, portfolio, alerts, risk
profile, prefs):

1. Visit `/privacy` in the running app.
2. Click **"Wipe all EquityScope data"**.

Or directly: open DevTools → Application → Local Storage → delete
every `equityscope.*` key.
