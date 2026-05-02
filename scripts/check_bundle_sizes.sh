#!/usr/bin/env bash
# Enforce JS / CSS bundle size budgets defined in PERFORMANCE.md.
# Fails the build if any actual size exceeds its budget. Update both
# this script AND PERFORMANCE.md when intentionally raising a budget.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ERRORS=0

# Budgets in BYTES. Keep in lockstep with PERFORMANCE.md.
declare -a CHECKS=(
  # path|budget_bytes|label
  "static/ui.js|7168|ui.js (≤ 7 KB)"
  "static/format.js|6144|format.js (≤ 6 KB)"
  "static/consent.js|4096|consent.js (≤ 4 KB)"
  "static/explainer.js|25600|explainer.js (≤ 25 KB)"
  "static/watchlist.js|4096|watchlist.js (≤ 4 KB)"
  "static/portfolio.js|7168|portfolio.js (≤ 7 KB)"
  "static/alerts.js|14336|alerts.js (≤ 14 KB)"
  "static/risk_profile.js|6144|risk_profile.js (≤ 6 KB)"
  "static/style.css|8192|style.css (≤ 8 KB)"
  "static/screener.css|26624|screener.css (≤ 26 KB)"
  "static/analysis.css|18432|analysis.css (≤ 18 KB)"
  "static/landing.css|10240|landing.css (≤ 10 KB)"
)

for entry in "${CHECKS[@]}"; do
  IFS='|' read -r path budget label <<< "$entry"
  if [[ ! -f "$path" ]]; then
    echo "  ✗ $label — file missing: $path"
    ERRORS=$((ERRORS + 1))
    continue
  fi
  actual=$(wc -c < "$path" | tr -d ' ')
  if (( actual <= budget )); then
    echo "  ✓ $label — ${actual} B"
  else
    echo "  ✗ $label — ${actual} B exceeds budget ${budget} B"
    ERRORS=$((ERRORS + 1))
  fi
done

echo ""
if (( ERRORS > 0 )); then
  echo "❌ $ERRORS bundle(s) over budget. Either trim, or update both"
  echo "   scripts/check_bundle_sizes.sh AND PERFORMANCE.md."
  exit 1
fi
echo "✅ All bundles within budget."
