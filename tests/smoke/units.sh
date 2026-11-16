#!/usr/bin/env bash
# Runs every unit file against the driver and fails if any of them fails. The same command runs
# locally before each commit and in CI (.github/workflows/tests.yml).
set -u
cd "$(dirname "$0")/../.." || exit 1
fail=0
for f in tests/smoke/unit*.py; do
  [ -n "${GITHUB_ACTIONS:-}" ] && echo "::group::$f"
  python3 -I "$f" contrib-one/bin/contrib-run || {
    [ -n "${GITHUB_ACTIONS:-}" ] && echo "::error::$f failed"
    echo "FAILED: $f"; fail=1; }
  [ -n "${GITHUB_ACTIONS:-}" ] && echo "::endgroup::"
done
[ "$fail" = 0 ] && echo "UNITS PASS" || echo "UNITS FAIL"
exit "$fail"
