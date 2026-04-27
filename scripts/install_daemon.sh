#!/usr/bin/env bash
# Install the always-on macOS LaunchDaemon for browser-only access.
# Requires sudo (called via osascript by Install-Browser-Mode.command).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.equityscope.global"
PLIST_DEST="/Library/LaunchDaemons/${LABEL}.plist"
TEMPLATE="$ROOT/scripts/${LABEL}.plist.template"

if [[ $EUID -ne 0 ]]; then
  echo "❌ Must run as root (use Install-Browser-Mode.command for GUI prompt)."
  exit 1
fi

# Resolve a stable Python interpreter; prefer system Python3 then /usr/local then Homebrew.
PYTHON="$(command -v python3 || true)"
if [[ -z "$PYTHON" ]]; then
  echo "❌ python3 not found in PATH"
  exit 1
fi

# Ensure required dependencies are installed for the resolved interpreter.
if ! "$PYTHON" -c "import flask, pandas, requests, yfinance" >/dev/null 2>&1; then
  echo "📦 Installing dependencies via $PYTHON ..."
  "$PYTHON" -m pip install --quiet -r "$ROOT/requirements.txt"
fi

# Ensure cert exists (run cert-gen as the invoking user, not root).
if [[ ! -f "$ROOT/certs/cert.pem" || ! -f "$ROOT/certs/key.pem" ]]; then
  echo "🔒 Generating self-signed cert..."
  if [[ -n "${SUDO_USER:-}" ]]; then
    sudo -u "$SUDO_USER" bash "$ROOT/scripts/gen_cert.sh"
  else
    bash "$ROOT/scripts/gen_cert.sh"
  fi
fi

# Ensure /etc/hosts entry.
if ! grep -qiF "Global-Stock-Analyser" /etc/hosts; then
  echo "" >> /etc/hosts
  echo "# EquityScope local mapping" >> /etc/hosts
  echo "127.0.0.1 Global-Stock-Analyser" >> /etc/hosts
  echo "✅ Added /etc/hosts entry"
fi

# Render plist template.
TMP_PLIST="$(mktemp)"
sed -e "s|__PYTHON__|${PYTHON}|g" \
    -e "s|__PROJECT_ROOT__|${ROOT}|g" \
    "$TEMPLATE" > "$TMP_PLIST"

# Bootout existing if present.
if launchctl print "system/${LABEL}" >/dev/null 2>&1; then
  echo "🔄 Removing existing daemon..."
  launchctl bootout "system/${LABEL}" 2>/dev/null || true
fi

# Install + load.
install -m 0644 -o root -g wheel "$TMP_PLIST" "$PLIST_DEST"
rm -f "$TMP_PLIST"

launchctl bootstrap system "$PLIST_DEST"
launchctl enable "system/${LABEL}"
launchctl kickstart -k "system/${LABEL}"

# Wait for the server to actually accept HTTPS.
echo -n "⏳ Waiting for server to come up"
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if curl -kfs --max-time 1 https://Global-Stock-Analyser/Local/ -o /dev/null; then
    echo ""
    echo "✅ Daemon installed and serving https://Global-Stock-Analyser/Local"
    exit 0
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "⚠️  Daemon installed but did not respond within 15s."
echo "    Check /var/log/global-stock-analyser.err.log"
exit 1
