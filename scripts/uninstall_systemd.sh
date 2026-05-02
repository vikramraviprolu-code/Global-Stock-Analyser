#!/usr/bin/env bash
# Remove the EquityScope systemd service + install dir.
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "❌ Run with sudo." >&2
  exit 1
fi

SERVICE_NAME="equityscope.service"
SERVICE_UNIT="/etc/systemd/system/$SERVICE_NAME"
INSTALL_DIR="/opt/equityscope"

echo "==> Stopping + disabling $SERVICE_NAME"
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true

if [[ -f "$SERVICE_UNIT" ]]; then
  rm -f "$SERVICE_UNIT"
  echo "    Removed $SERVICE_UNIT"
fi

systemctl daemon-reload

if [[ -d "$INSTALL_DIR" ]]; then
  rm -rf "$INSTALL_DIR"
  echo "    Removed $INSTALL_DIR"
fi

echo ""
echo "✅ EquityScope systemd service removed."
