#!/usr/bin/env bash
# Run pip-audit against requirements.txt and surface vulnerabilities.
# Pending upstream fixes (no patched release on PyPI yet) are listed in
# AUDIT_IGNORE — these MUST be reviewed at every release. Drop entries
# from the list once the fix lands.
#
# Usage:
#   bash scripts/audit_dependencies.sh           # fail on any *new* CVE
#   bash scripts/audit_dependencies.sh --strict  # fail on any CVE incl. ignored
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# --- Pending upstream — review every release ---------------------------------
# GHSA-gc5v-m9x4-r6x2  requests<2.33.0       (no fix on PyPI as of 2026-05-02)
# GHSA-qw2m-4pqf-rmpp  curl-cffi<0.15.0      (no fix on PyPI as of 2026-05-02)
AUDIT_IGNORE=(
  "--ignore-vuln=GHSA-gc5v-m9x4-r6x2"
  "--ignore-vuln=GHSA-qw2m-4pqf-rmpp"
)

if [[ "${1:-}" == "--strict" ]]; then
  AUDIT_IGNORE=()
fi

echo "Running pip-audit on requirements.txt …"
python3 -m pip_audit -r requirements.txt "${AUDIT_IGNORE[@]}"
RESULT=$?

if [[ $RESULT -eq 0 ]]; then
  echo ""
  echo "✅ No actionable vulnerabilities. Pending upstream:"
  for entry in "${AUDIT_IGNORE[@]}"; do
    echo "   - ${entry#--ignore-vuln=}"
  done
fi

exit $RESULT
