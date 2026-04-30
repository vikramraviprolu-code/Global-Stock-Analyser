#!/usr/bin/env bash
# Validates that the same version string appears in every place it should.
# Run before every release commit — failing here blocks the push.
#
# See RELEASING.md for the full release checklist.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Source-of-truth: pyproject.toml
PY_VER="$(grep -E '^version = ' pyproject.toml | sed -E 's/version = "(.+)"/\1/')"
if [[ -z "$PY_VER" ]]; then
  echo "❌ Could not parse pyproject.toml version."
  exit 1
fi

echo "Source of truth (pyproject.toml): $PY_VER"
echo ""

ERRORS=0

check() {
  local label="$1"
  local file="$2"
  local pattern="$3"
  local expected="$4"
  local actual
  actual="$(grep -oE "$pattern" "$file" | head -1 || true)"
  if [[ "$actual" == "$expected" ]]; then
    echo "  ✓ $label"
  else
    echo "  ✗ $label — expected '$expected', got '$actual' in $file"
    ERRORS=$((ERRORS + 1))
  fi
}

echo "Checking version pins:"

# app.py — /api/settings/server-info
check "app.py /api/settings/server-info" \
  "app.py" \
  '"version": "[0-9]+\.[0-9]+\.[0-9]+"' \
  "\"version\": \"$PY_VER\""

# README — version badge
check "README version badge" \
  "README.md" \
  'version-[0-9]+\.[0-9]+\.[0-9]+' \
  "version-$PY_VER"

# README — What's new section
README_WHATSNEW="$(grep -oE "What's new in v[0-9]+\.[0-9]+\.[0-9]+" README.md | head -1 || true)"
if [[ "$README_WHATSNEW" == "What's new in v$PY_VER" ]]; then
  echo "  ✓ README \"What's new in vX.Y.Z\" header"
else
  echo "  ✗ README \"What's new in\" header — expected 'v$PY_VER', got '$README_WHATSNEW'"
  ERRORS=$((ERRORS + 1))
fi

# SECURITY — Latest version line
check "SECURITY.md Latest line" \
  "SECURITY.md" \
  'Latest: \*\*v[0-9]+\.[0-9]+\.[0-9]+\*\*' \
  "Latest: **v$PY_VER**"

# CHANGELOG — top entry
CHANGELOG_TOP="$(grep -oE "## \[[0-9]+\.[0-9]+\.[0-9]+\]" CHANGELOG.md | head -1 || true)"
if [[ "$CHANGELOG_TOP" == "## [$PY_VER]" ]]; then
  echo "  ✓ CHANGELOG.md top entry"
else
  echo "  ✗ CHANGELOG.md — expected top entry '## [$PY_VER]', got '$CHANGELOG_TOP'"
  ERRORS=$((ERRORS + 1))
fi

echo ""
if (( ERRORS > 0 )); then
  echo "❌ $ERRORS version pin(s) out of sync. Fix before committing."
  echo "   See RELEASING.md for the full release checklist."
  exit 1
fi
echo "✅ All version pins match $PY_VER. Ready to commit + tag + push."
