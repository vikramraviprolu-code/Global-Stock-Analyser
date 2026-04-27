#!/usr/bin/env bash
# Double-click to remove the always-on browser-launch daemon.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
UNINSTALL="/tmp/equityscope_uninstall_$$.sh"
MKCERT_BIN="$ROOT/bin/mkcert"

cleanup() { rm -f "$UNINSTALL"; }
trap cleanup EXIT

echo "🛑 Removing always-on browser mode..."

# 1. Remove mkcert local CA from the user's login keychain (no sudo).
if [[ -x "$MKCERT_BIN" ]]; then
  echo "🔐 Removing mkcert local CA from your login keychain..."
  "$MKCERT_BIN" -uninstall || true
fi

# 2. Stage uninstaller to /tmp (elevated process can't read iCloud)
cp "$ROOT/scripts/uninstall_daemon.sh" "$UNINSTALL"
chmod +x "$UNINSTALL"

/usr/bin/osascript <<EOF
do shell script "bash '$UNINSTALL'" with administrator privileges
EOF

echo ""
echo "✅ Daemon removed. https://Global-Stock-Analyser/Local will no longer respond"
echo "   until you reinstall."
