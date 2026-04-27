#!/usr/bin/env bash
# Add `127.0.0.1 Global-Stock-Analyser` to /etc/hosts (idempotent).
# Requires sudo.
set -euo pipefail

APP_HOSTNAME="${APP_HOSTNAME:-Global-Stock-Analyser}"
ENTRY="127.0.0.1 ${APP_HOSTNAME}"

if grep -qi "[[:space:]]${APP_HOSTNAME}\(\$\|[[:space:]]\)" /etc/hosts; then
  echo "✅ /etc/hosts already maps ${APP_HOSTNAME}"
  exit 0
fi

if [[ $EUID -ne 0 ]]; then
  echo "Need sudo to write /etc/hosts. Re-running with sudo..."
  exec sudo "$0" "$@"
fi

echo "" >> /etc/hosts
echo "# EquityScope local mapping" >> /etc/hosts
echo "$ENTRY" >> /etc/hosts
echo "✅ Added: $ENTRY"
