#!/usr/bin/env bash
# Remove the always-on macOS LaunchDaemon and clean up /usr/local install.
set -euo pipefail

LABEL="com.equityscope.global"
PLIST_DEST="/Library/LaunchDaemons/${LABEL}.plist"
DEST="/usr/local/global-stock-analyser"

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

# Uninstall mkcert local CA before deleting the project tree (so mkcert -uninstall
# can find its CAROOT). Best effort.
MKCERT_BIN="$DEST/bin/mkcert"
if [[ -x "$MKCERT_BIN" ]]; then
  echo "🔐 Removing mkcert local CA from trust store..."
  "$MKCERT_BIN" -uninstall 2>/dev/null || true
fi

if [[ -d "$DEST" ]]; then
  rm -rf "$DEST"
  echo "🗑️  Removed $DEST"
fi

# Remove the leaf cert from System keychain (only meaningful if openssl fallback was used)
security delete-certificate -c "Global-Stock-Analyser" \
  /Library/Keychains/System.keychain 2>/dev/null && \
  echo "🗑️  Removed leaf cert from System keychain" || true

echo "✅ Browser auto-launch disabled."
echo "   /etc/hosts entry left in place. Remove manually if desired:"
echo "     sudo sed -i '' '/Global-Stock-Analyser/d' /etc/hosts"
