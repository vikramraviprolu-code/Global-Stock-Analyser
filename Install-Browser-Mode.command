#!/usr/bin/env bash
# Double-click to install the always-on browser-launch daemon.
# After install: opening https://Global-Stock-Analyser/Local just works,
# no Terminal, no double-clicking, no relaunching.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
INSTALL_SCRIPT="$ROOT/scripts/install_daemon.sh"
URL="https://Global-Stock-Analyser/Local"

echo "🚀 Installing always-on browser mode..."
echo "   This needs admin rights (port 443 binding + LaunchDaemon)."
echo ""

# Use osascript so macOS shows a native password dialog.
/usr/bin/osascript <<EOF
do shell script "bash '$INSTALL_SCRIPT'" with administrator privileges
EOF

# Open browser.
echo ""
echo "🌐 Opening $URL ..."
open "$URL"

echo ""
echo "✅ Done. From now on, just open $URL — the server is always available."
echo "   To uninstall later, double-click Uninstall-Browser-Mode.command"
