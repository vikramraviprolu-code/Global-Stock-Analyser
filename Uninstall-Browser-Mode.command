#!/usr/bin/env bash
# Double-click to remove the always-on browser-launch daemon.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$ROOT/scripts/uninstall_daemon.sh"

echo "🛑 Removing always-on browser mode..."
/usr/bin/osascript <<EOF
do shell script "bash '$SCRIPT'" with administrator privileges
EOF

echo ""
echo "✅ Daemon removed. The URL https://Global-Stock-Analyser/Local will no longer respond"
echo "   until you reinstall or use Global-Stock-Analyser.command (manual mode)."
