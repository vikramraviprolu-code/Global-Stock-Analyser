# Clean-machine install audit

Reproducible smoke checklist for verifying EquityScope installs cleanly
on a fresh macOS host. Run before tagging any release that touches
`scripts/install_daemon.sh`, `scripts/gen_cert.sh`, `scripts/setup_hosts.sh`,
or any path referenced by the LaunchDaemon plist.

This is the **third party reproducibility gate** before the project
promotes to v1.0.

## Target environments

| Tier | macOS | Python | Hardware | Status |
| --- | --- | --- | --- | --- |
| Primary | 14 (Sonoma) on Apple Silicon | 3.9 system | M-series | Reference dev box (this repo's home) |
| Primary | 15 (Sequoia) on Apple Silicon | 3.12 (homebrew) | M-series | Required for v1.0 |
| Secondary | 14 / 15 on Intel | 3.11 | x86_64 | Best-effort — not blocking |

## Pre-flight

On the target machine **before** running the installer:

- [ ] Fresh user account or at least an account that has never installed EquityScope.
- [ ] `/usr/local/global-stock-analyser/` does not exist.
- [ ] `~/Library/LaunchAgents/com.equityscope.global.plist` does not exist.
- [ ] `~/Library/Application Support/mkcert/` does not exist or has been wiped.
- [ ] No prior `Global-Stock-Analyser` row in `/etc/hosts`.
- [ ] System keychain has no `Global-Stock-Analyser` certificate.
- [ ] Browser History / HSTS state cleared for `Global-Stock-Analyser` (Chrome: `chrome://net-internals/#hsts → Delete domain security policies`).

## Install steps

In order:

```bash
git clone https://github.com/vikramraviprolu-code/Global-Stock-Analyser.git
cd Global-Stock-Analyser
python3 -m pip install -r requirements.txt
sudo bash scripts/install_daemon.sh
```

Each prompt → record the response.

- [ ] `install_daemon.sh` prints "Project staged at /tmp/equityscope_stage_*"
- [ ] mkcert local CA installed without permission errors
- [ ] Leaf cert generated for `Global-Stock-Analyser`
- [ ] `/etc/hosts` row added (verify: `grep Global-Stock-Analyser /etc/hosts`)
- [ ] LaunchDaemon loaded (verify: `sudo launchctl list | grep equityscope`)
- [ ] Daemon starts within 10 seconds (verify: `curl -fsS https://Global-Stock-Analyser/Local/api/settings/server-info | jq .version`)
- [ ] Returned version equals the `pyproject.toml` version pin

## First-launch checks

Open `https://Global-Stock-Analyser/Local` in Chrome / Safari / Firefox:

- [ ] **Green padlock** in all three browsers (no Advanced → Proceed flow).
- [ ] Landing page renders within 1.5 s.
- [ ] **Consent banner** appears on first visit; clicking "Accept" persists across reload.
- [ ] **Decline** wipes every `equityscope.*` localStorage key (DevTools → Application → Local Storage).

## Smoke tour (post-consent)

- [ ] `/screener` — preset list loads from `/api/screener/presets`, "Run preset: Cheap large-cap value" returns at least 5 rows in under 8 s.
- [ ] `/app?ticker=AAPL` — all 8 tabs render: Snapshot, Chart, Value, Momentum, Peers, Events, Recommendation, Sources.
- [ ] Recommendation tab shows the **bucket chip** ("Tuned for Balanced · Buy ≥ M65/V40/R≤50 · change") — added v0.22.1.
- [ ] `/risk-profile` — answer 10 questions → score saved → bucket label visible.
- [ ] Re-run `/app?ticker=AAPL` → Recommendation thresholds change to match the new bucket (visible in the chip + reasons text).
- [ ] `/watchlists` — add AAPL + MSFT → click `↓ CSV` → file downloads with 20 columns and 3 lines (header + 2 tickers).
- [ ] `/watchlists` — `↓ JSON` exports `{watchlist, exportedAt, tickers, metrics}`.
- [ ] `/alerts` — create a price-cross alert → switch to a different page → verify polling hits the API every ~60 s (DevTools → Network).
- [ ] `/portfolio` — add AAPL with cost basis → portfolio P/L renders with currency conversion.
- [ ] `/news?ticker=AAPL` — sentiment digest appears with at least 3 headlines.
- [ ] `/events?ticker=AAPL` — calendar surface earnings + dividend dates if available.
- [ ] `/data-quality` — every metric carries a source name + freshness chip.
- [ ] `/sources` — every metric in the analysis page has a clickable provider URL.
- [ ] `/.well-known/security.txt` — RFC 9116 fields present, `Expires` is in the future.

## Cross-page state checks

- [ ] Refresh on `/watchlists` → watchlists persist.
- [ ] Quit + relaunch browser → watchlists, portfolio, alerts, risk profile all survive.
- [ ] Quit + relaunch the daemon (`sudo launchctl unload && load` on the plist) → in-memory caches reset; localStorage state untouched.
- [ ] DevTools → Application → Local Storage shows only `equityscope.*` keys (no third-party cookies).

## Security checks

- [ ] Headers on every HTML route (verify with `curl -sI`):
  - `Content-Security-Policy: default-src 'self'; … frame-ancestors 'none'`
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: no-referrer`
  - `Permissions-Policy: geolocation=(), microphone=(), camera=()`
  - `Server: EquityScope` (no Werkzeug + Python banner)
  - `Server-Timing: app;dur=<ms>`
- [ ] `POST /api/shutdown` from a cross-origin Origin header returns HTTP 403.
- [ ] `POST /api/settings/clear-cache` from a cross-origin Origin header returns HTTP 403.
- [ ] Cert chain in keychain shows mkcert local CA as the issuer.
- [ ] No connection attempts to any non-`Global-Stock-Analyser` domain in DevTools → Network on a typical analyse-AAPL flow (Stooq + yfinance go through the server, not the browser).

## Uninstall

- [ ] `sudo bash scripts/uninstall_daemon.sh` removes:
  - `/usr/local/global-stock-analyser/`
  - `~/Library/LaunchAgents/com.equityscope.global.plist`
  - `/etc/hosts` row
  - LaunchDaemon registration
- [ ] Optional: `mkcert -uninstall` removes the local CA from the keychain.

## Reporting

Filed the audit on a clean machine? Open an issue tagged
`install-audit` with:

- macOS version
- Apple Silicon vs Intel
- Python version
- Browser(s) tested
- Any failed checkbox + a one-line reason
- Total wall-clock time from `git clone` to first green padlock

Issues filed against the audit checklist itself (e.g. "step 7 ambiguous")
are equally welcome — this file is the project's user-facing install
contract.
