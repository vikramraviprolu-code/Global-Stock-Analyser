#!/usr/bin/env bash
# Double-click to add the EquityScope self-signed cert to the macOS System
# keychain trust store. After this, browsers stop showing
# "Your connection is not private" / NET::ERR_CERT_AUTHORITY_INVALID
# for https://Global-Stock-Analyser/Local.
set -euo pipefail

CERT="/usr/local/global-stock-analyser/certs/cert.pem"

if [[ ! -f "$CERT" ]]; then
  echo "❌ Cert not found at $CERT"
  echo "   Run Install-Browser-Mode.command first."
  exit 1
fi

echo "🔐 Adding cert to System keychain..."
echo "   You'll see a macOS password dialog."

/usr/bin/osascript <<EOF
do shell script "security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain '$CERT'" with administrator privileges
EOF

echo ""
echo "✅ Cert trusted. Restart your browser, then open https://Global-Stock-Analyser/Local"
echo "   No more 'connection not private' warning."
