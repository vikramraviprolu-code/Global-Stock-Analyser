#!/usr/bin/env bash
# Launch app over HTTPS at https://Global-Stock-Analyser/Local
# Generates certs if missing. Defaults to port 443 (sudo). Use PORT=8443 to skip sudo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOSTNAME="${HOSTNAME:-Global-Stock-Analyser}"
PORT="${PORT:-443}"
URL_PREFIX="${URL_PREFIX:-/Local}"
HOST="${HOST:-0.0.0.0}"

# 1. Ensure certs exist
if [[ ! -f "$ROOT/certs/cert.pem" || ! -f "$ROOT/certs/key.pem" ]]; then
  echo "🔒 Generating self-signed cert..."
  bash "$ROOT/scripts/gen_cert.sh"
fi

# 2. Verify hosts entry
if ! grep -qi "[[:space:]]${HOSTNAME}\(\$\|[[:space:]]\)" /etc/hosts; then
  echo "⚠️  /etc/hosts missing entry for ${HOSTNAME}."
  echo "   Run: sudo bash $ROOT/scripts/setup_hosts.sh"
  exit 1
fi

# 3. If port < 1024, need sudo to bind
NEED_SUDO=""
if (( PORT < 1024 && EUID != 0 )); then
  NEED_SUDO="sudo -E"
fi

export HOST PORT URL_PREFIX
export SSL_CERT="$ROOT/certs/cert.pem"
export SSL_KEY="$ROOT/certs/key.pem"
export TRUSTED_HOSTS="${TRUSTED_HOSTS:-127.0.0.1,localhost,${HOSTNAME,,}}"

cd "$ROOT"
echo "🚀 https://${HOSTNAME}:${PORT}${URL_PREFIX}  (Ctrl-C to stop)"
exec $NEED_SUDO python3 -W ignore app.py
