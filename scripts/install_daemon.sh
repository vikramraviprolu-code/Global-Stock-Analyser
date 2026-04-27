#!/usr/bin/env bash
# Install the always-on macOS LaunchDaemon for browser-only access.
# Called as root via osascript from Install-Browser-Mode.command.
#
# Usage: install_daemon.sh <stage_dir>
#   <stage_dir> contains a non-iCloud copy of the project (rsynced by the
#   user-level launcher). Required because elevated processes are blocked
#   by macOS TCC from reading iCloud Drive paths.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "❌ Must run as root."
  exit 1
fi

STAGE="${1:-}"
if [[ -z "$STAGE" || ! -d "$STAGE" ]]; then
  echo "❌ Missing stage directory argument."
  exit 1
fi

LABEL="com.equityscope.global"
DEST="/usr/local/global-stock-analyser"
PLIST_DEST="/Library/LaunchDaemons/${LABEL}.plist"

# 1. Mirror staged project to /usr/local (preserve venv/ and certs/ between installs)
echo "📦 Installing to $DEST"
mkdir -p "$DEST"
rsync -a --delete \
      --exclude '.git' --exclude '__pycache__' --exclude 'tests' \
      --exclude '*.command' --exclude 'certs' --exclude 'venv' \
      "$STAGE/" "$DEST/"
chmod +x "$DEST/scripts/"*.sh 2>/dev/null || true
chown -R root:wheel "$DEST"

# 2. Build a self-contained virtualenv inside DEST so the daemon doesn't depend
#    on user-site packages (which root can't see) and survives Python upgrades.
SYSTEM_PYTHON="$(command -v python3 || true)"
if [[ -z "$SYSTEM_PYTHON" ]]; then
  echo "❌ python3 not found in PATH"
  exit 1
fi
VENV="$DEST/venv"
PYTHON="$VENV/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "🐍 Creating venv at $VENV"
  "$SYSTEM_PYTHON" -m venv "$VENV"
fi
echo "📦 Installing Python deps into venv"
"$PYTHON" -m pip install --quiet --upgrade pip
"$PYTHON" -m pip install --quiet -r "$DEST/requirements.txt"
"$PYTHON" -c "import flask, pandas, requests, yfinance" || {
  echo "❌ Dependency install failed"
  exit 1
}

# 3. Generate self-signed cert if missing
mkdir -p "$DEST/certs"
if [[ ! -f "$DEST/certs/cert.pem" || ! -f "$DEST/certs/key.pem" ]]; then
  echo "🔒 Generating self-signed cert..."
  openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 365 \
    -keyout "$DEST/certs/key.pem" -out "$DEST/certs/cert.pem" \
    -subj "/CN=Global-Stock-Analyser" \
    -addext "subjectAltName=DNS:Global-Stock-Analyser,DNS:localhost,IP:127.0.0.1" \
    -addext "extendedKeyUsage=serverAuth" 2>/dev/null
  chmod 600 "$DEST/certs/key.pem"
  chmod 644 "$DEST/certs/cert.pem"
fi

# 4. /etc/hosts mapping
if ! grep -qiF "Global-Stock-Analyser" /etc/hosts; then
  printf "\n# EquityScope local mapping\n127.0.0.1 Global-Stock-Analyser\n" >> /etc/hosts
  echo "✅ Added /etc/hosts entry"
fi

# 5. Render plist
TEMPLATE="$DEST/scripts/${LABEL}.plist.template"
if [[ ! -f "$TEMPLATE" ]]; then
  echo "❌ plist template missing at $TEMPLATE"
  exit 1
fi
sed -e "s|__PYTHON__|${PYTHON}|g" \
    -e "s|__PROJECT_ROOT__|${DEST}|g" \
    "$TEMPLATE" > "$PLIST_DEST"
chown root:wheel "$PLIST_DEST"
chmod 644 "$PLIST_DEST"

# 6. Bootstrap daemon (idempotent)
if launchctl print "system/${LABEL}" >/dev/null 2>&1; then
  echo "🔄 Replacing existing daemon..."
  launchctl bootout "system/${LABEL}" 2>/dev/null || true
fi
launchctl bootstrap system "$PLIST_DEST"
launchctl enable "system/${LABEL}"
launchctl kickstart -k "system/${LABEL}"

# 7. Wait for HTTPS readiness
echo -n "⏳ Waiting for server"
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if curl -kfs --max-time 1 https://Global-Stock-Analyser/Local/ -o /dev/null; then
    echo ""
    echo "✅ Daemon serving https://Global-Stock-Analyser/Local"
    exit 0
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "⚠️  Daemon installed but did not respond within 15s."
echo "    Logs: /var/log/global-stock-analyser.err.log"
exit 1
