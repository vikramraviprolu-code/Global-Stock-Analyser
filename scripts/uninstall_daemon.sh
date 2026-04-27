#!/usr/bin/env bash
# Remove the always-on macOS LaunchDaemon.
set -euo pipefail

LABEL="com.equityscope.global"
PLIST_DEST="/Library/LaunchDaemons/${LABEL}.plist"

if [[ $EUID -ne 0 ]]; then
  echo "❌ Must run as root."
  exit 1
fi

if launchctl print "system/${LABEL}" >/dev/null 2>&1; then
  launchctl bootout "system/${LABEL}" 2>/dev/null || true
  echo "🛑 Stopped daemon"
fi

if [[ -f "$PLIST_DEST" ]]; then
  rm -f "$PLIST_DEST"
  echo "🗑️  Removed $PLIST_DEST"
fi

echo "✅ Browser auto-launch disabled."
echo "   /etc/hosts and certs were left in place. Remove manually if desired."
