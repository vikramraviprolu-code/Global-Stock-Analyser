#!/usr/bin/env bash
# Install EquityScope as a systemd user service on Linux.
# Mirrors the macOS LaunchDaemon installer (scripts/install_daemon.sh) for
# Linux hosts. Loopback-only, hardened, journald logs.
#
# Usage:
#   sudo bash scripts/install_systemd.sh
#
# Uninstall:
#   sudo bash scripts/uninstall_systemd.sh
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "❌ Run with sudo." >&2
  exit 1
fi

INSTALL_USER="${SUDO_USER:-$USER}"
INSTALL_GROUP="$(id -gn "$INSTALL_USER")"
INSTALL_DIR="/opt/equityscope"
SERVICE_NAME="equityscope.service"
SERVICE_UNIT="/etc/systemd/system/$SERVICE_NAME"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> EquityScope systemd installer"
echo "    User:        $INSTALL_USER"
echo "    Group:       $INSTALL_GROUP"
echo "    Install dir: $INSTALL_DIR"
echo "    Source:      $ROOT"
echo ""

# 1. Stage the project at $INSTALL_DIR
echo "==> Staging project at $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
rsync -a --delete \
    --exclude=".git" --exclude="__pycache__" --exclude="*.pyc" \
    --exclude="audit" --exclude=".github" --exclude="tests" \
    "$ROOT/" "$INSTALL_DIR/"
chown -R "$INSTALL_USER:$INSTALL_GROUP" "$INSTALL_DIR"

# 2. Create venv + install
echo "==> Creating virtualenv + installing dependencies"
sudo -u "$INSTALL_USER" python3 -m venv "$INSTALL_DIR/venv"
sudo -u "$INSTALL_USER" "$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$INSTALL_USER" "$INSTALL_DIR/venv/bin/pip" install --quiet \
    -r "$INSTALL_DIR/requirements.txt" waitress

# Make `equityscope` console script available inside the venv
sudo -u "$INSTALL_USER" "$INSTALL_DIR/venv/bin/pip" install --quiet -e "$INSTALL_DIR"

# 3. Render the service file from the template
echo "==> Writing $SERVICE_UNIT"
sed -e "s|__USER__|$INSTALL_USER|g" \
    -e "s|__GROUP__|$INSTALL_GROUP|g" \
    -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
    "$INSTALL_DIR/scripts/equityscope.service.template" > "$SERVICE_UNIT"
chmod 0644 "$SERVICE_UNIT"

# 4. Reload + enable + start
echo "==> Enabling + starting service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# 5. Smoke check
sleep 3
if systemctl is-active --quiet "$SERVICE_NAME"; then
  echo ""
  echo "✅ EquityScope is running."
  echo "   Open: http://127.0.0.1:5050"
  echo "   Logs: journalctl -u $SERVICE_NAME -f"
  echo "   Stop: sudo systemctl stop $SERVICE_NAME"
else
  echo ""
  echo "❌ Service failed to start. Check: journalctl -u $SERVICE_NAME -n 50"
  exit 1
fi
