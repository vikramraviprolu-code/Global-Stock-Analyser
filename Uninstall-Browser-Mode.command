#!/usr/bin/env bash
# Double-click to remove the always-on browser-launch daemon.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
UNINSTALL="/tmp/equityscope_uninstall_$$.sh"

cleanup() { rm -f "$UNINSTALL"; }
trap cleanup EXIT

echo "🛑 Removing always-on browser mode..."

# Stage uninstall script to /tmp (elevated process can't read iCloud)
cp "$ROOT/scripts/uninstall_daemon.sh" "$UNINSTALL"
chmod +x "$UNINSTALL"

/usr/bin/osascript <<EOF
do shell script "bash '$UNINSTALL'" with administrator privileges
EOF

echo ""
echo "✅ Daemon removed. https://Global-Stock-Analyser/Local will no longer respond"
echo "   until you reinstall."
