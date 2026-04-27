#!/usr/bin/env bash
# Double-click to install always-on browser mode.
#
# Strategy:
#   1. As the logged-in user (no sudo): download mkcert, install its local CA
#      into the user's login keychain, and issue a leaf cert. This must run
#      as the user because macOS blocks trust changes from non-interactive
#      elevated contexts (the "authorization was denied since no user
#      interaction was possible" error).
#   2. Stage the project + freshly issued cert to /tmp (outside iCloud).
#   3. osascript admin runs install_daemon.sh which copies everything to
#      /usr/local/global-stock-analyser, builds a venv, and bootstraps the
#      LaunchDaemon on port 443.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
URL="https://Global-Stock-Analyser/Local"
STAGE="/tmp/equityscope_stage_$$"
CERT_DIR="/tmp/equityscope_certs_$$"
INSTALL="/tmp/equityscope_install_$$.sh"
MKCERT_VERSION="v1.4.4"

cleanup() { rm -rf "$STAGE" "$CERT_DIR" "$INSTALL"; }
trap cleanup EXIT

echo "🚀 Installing always-on browser mode..."
echo ""

# 1. Download mkcert (user-level, no sudo)
ARCH="$(uname -m)"
case "$ARCH" in
  arm64)  MKCERT_ARCH="darwin-arm64" ;;
  x86_64) MKCERT_ARCH="darwin-amd64" ;;
  *)
    echo "❌ Unsupported architecture: $ARCH"
    exit 1 ;;
esac

MKCERT_BIN="$ROOT/bin/mkcert"
mkdir -p "$ROOT/bin"

if [[ ! -x "$MKCERT_BIN" ]]; then
  echo "📥 Downloading mkcert $MKCERT_VERSION ($MKCERT_ARCH)..."
  curl -fsSL --max-time 60 -o "$MKCERT_BIN" \
    "https://github.com/FiloSottile/mkcert/releases/download/${MKCERT_VERSION}/mkcert-${MKCERT_VERSION}-${MKCERT_ARCH}"
  chmod +x "$MKCERT_BIN"
fi

# 1b. Heal an orphaned mkcert CAROOT from a prior failed install. Older
#     versions of this installer ran mkcert under sudo, which left
#     ~/Library/Application Support/mkcert root-owned and unreadable by
#     the user. Detect and remove via a single admin prompt.
MKCERT_CAROOT="$HOME/Library/Application Support/mkcert"
if [[ -d "$MKCERT_CAROOT" ]]; then
  CAROOT_OWNER_UID="$(stat -f %u "$MKCERT_CAROOT" 2>/dev/null || echo 0)"
  if [[ "$CAROOT_OWNER_UID" != "$(id -u)" ]]; then
    echo "🔧 Removing orphaned root-owned mkcert CAROOT from a prior failed install..."
    /usr/bin/osascript <<EOF
do shell script "rm -rf '$MKCERT_CAROOT'" with administrator privileges
EOF
  fi
fi

# 2. Install local CA into the user's login keychain.
#    macOS may show a single keychain-unlock prompt the first time.
echo "🔐 Installing mkcert local CA into your login keychain..."
echo "    (You may see a keychain unlock prompt — this is normal.)"
"$MKCERT_BIN" -install

# 3. Issue a leaf cert
mkdir -p "$CERT_DIR"
echo "🔐 Issuing cert for Global-Stock-Analyser..."
"$MKCERT_BIN" -cert-file "$CERT_DIR/cert.pem" -key-file "$CERT_DIR/key.pem" \
  Global-Stock-Analyser localhost 127.0.0.1
chmod 600 "$CERT_DIR/key.pem"

# 4. Stage project to /tmp (osascript admin can't read iCloud)
echo "📂 Staging project to $STAGE"
mkdir -p "$STAGE"
rsync -a \
  --exclude '.git' --exclude '__pycache__' --exclude '.pytest_cache' \
  --exclude 'certs' --exclude 'tests' --exclude '*.command' \
  --exclude '.DS_Store' --exclude 'venv' \
  "$ROOT/" "$STAGE/"

# 5. Copy installer + plist template to /tmp too
cp "$ROOT/scripts/install_daemon.sh" "$INSTALL"
chmod +x "$INSTALL"

echo ""
echo "🔑 Now requesting admin rights for daemon install (port 443 + LaunchDaemon)..."

# 6. Run installer with admin privileges. Pass cert dir so it skips cert gen.
/usr/bin/osascript <<EOF
do shell script "USER_CERTS='$CERT_DIR' bash '$INSTALL' '$STAGE'" with administrator privileges
EOF

# 7. Open browser
echo ""
echo "🌐 Opening $URL"
open "$URL" || true

echo ""
echo "✅ Done. From now on, just open $URL in any browser — green padlock, no warnings."
echo "   Logs: /var/log/global-stock-analyser.err.log"
echo "   To uninstall: double-click Uninstall-Browser-Mode.command"
