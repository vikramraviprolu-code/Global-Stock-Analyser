#!/usr/bin/env bash
# Double-click launcher for macOS Finder.
#
# Behaviour:
#   - If the server is already running, just opens the browser.
#   - Otherwise prompts for the admin password via the macOS GUI dialog,
#     starts the HTTPS server in the background, then opens the browser.
#   - Server auto-shuts down ~45s after the last browser tab closes
#     (configurable via IDLE_TIMEOUT in app.py / run_secure.sh).
set -euo pipefail

# Resolve project root from this script's location, even if launched from Finder.
ROOT="$(cd "$(dirname "$0")" && pwd)"
URL="https://Global-Stock-Analyser/Local"
LOG="/tmp/global-stock-analyser.log"
HOSTS_SCRIPT="$ROOT/scripts/setup_hosts.sh"
RUN_SCRIPT="$ROOT/scripts/run_secure.sh"

# Already up? Just open the browser.
if curl -kfs --max-time 2 "$URL" -o /dev/null; then
  echo "Server already running — opening browser."
  open "$URL"
  exit 0
fi

# Ensure /etc/hosts has the entry (idempotent; needs sudo on first run).
if ! grep -qiF "Global-Stock-Analyser" /etc/hosts; then
  /usr/bin/osascript <<EOF
do shell script "bash '$HOSTS_SCRIPT'" with administrator privileges
EOF
fi

# Launch the HTTPS server detached, with admin privileges (port 443 needs root).
# Use osascript so macOS shows a native password dialog instead of a Terminal prompt.
/usr/bin/osascript <<EOF
do shell script "nohup bash '$RUN_SCRIPT' > '$LOG' 2>&1 &" with administrator privileges
EOF

# Wait up to 10s for the server to come up, then open the browser.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -kfs --max-time 1 "$URL" -o /dev/null; then
    open "$URL"
    exit 0
  fi
  sleep 1
done

echo "Server did not start within 10s. Check $LOG for errors."
open "$LOG"
exit 1
