#!/usr/bin/env bash
# Generate a self-signed TLS cert for local development.
# Output: certs/cert.pem and certs/key.pem (chmod 600 on the key).
# CN: Global-Stock-Analyser  |  SAN: Global-Stock-Analyser, localhost, 127.0.0.1
set -euo pipefail

HOSTNAME="${HOSTNAME:-Global-Stock-Analyser}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/certs"
mkdir -p "$DEST"

CERT="$DEST/cert.pem"
KEY="$DEST/key.pem"

if [[ -f "$CERT" && -f "$KEY" ]]; then
  echo "Certs already exist at $DEST. Delete to regenerate."
  exit 0
fi

openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 365 \
  -keyout "$KEY" -out "$CERT" \
  -subj "/CN=${HOSTNAME}" \
  -addext "subjectAltName=DNS:${HOSTNAME},DNS:localhost,IP:127.0.0.1" \
  -addext "extendedKeyUsage=serverAuth"

chmod 600 "$KEY"
chmod 644 "$CERT"

echo ""
echo "✅ Generated:"
echo "   cert: $CERT"
echo "   key:  $KEY"
echo ""
echo "Trust on macOS (optional, removes browser warning):"
echo "   sudo security add-trusted-cert -d -r trustRoot \\"
echo "     -k /Library/Keychains/System.keychain \"$CERT\""
