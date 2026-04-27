#!/usr/bin/env bash
# Double-click to install the always-on browser-launch daemon.
#
# Strategy: macOS TCC blocks elevated (sudo / osascript-with-admin) processes
# from reading iCloud Drive paths. We work around it by staging the project
# to /tmp first (user privileges, full iCloud access), then running the
# install script from /tmp under elevated privileges. The install script
# rsyncs to /usr/local/global-stock-analyser/ where the daemon will run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
URL="https://Global-Stock-Analyser/Local"
STAGE="/tmp/equityscope_stage_$$"
INSTALL="/tmp/equityscope_install_$$.sh"

cleanup() { rm -rf "$STAGE" "$INSTALL"; }
trap cleanup EXIT

echo "🚀 Installing always-on browser mode..."
echo "   You'll see a macOS password dialog (admin required for port 443 + LaunchDaemon)."
echo ""

# 1. Stage the project to /tmp (skip git, caches, certs — those are regenerated)
echo "📂 Staging project to $STAGE"
mkdir -p "$STAGE"
rsync -a \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'certs' \
  --exclude 'tests' \
  --exclude '*.command' \
  --exclude '.DS_Store' \
  "$ROOT/" "$STAGE/"

# 2. Copy the install script to /tmp too (elevated process can't read iCloud)
cp "$ROOT/scripts/install_daemon.sh" "$INSTALL"
chmod +x "$INSTALL"

# 3. Run installer with admin privileges via osascript GUI dialog
/usr/bin/osascript <<EOF
do shell script "bash '$INSTALL' '$STAGE'" with administrator privileges
EOF

# 4. Open browser
echo ""
echo "🌐 Opening $URL"
open "$URL" || true

echo ""
echo "✅ Done. From now on, just open $URL in any browser — the server is always available."
echo "   Logs: /var/log/global-stock-analyser.err.log"
echo "   To uninstall: double-click Uninstall-Browser-Mode.command"
