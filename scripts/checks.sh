#!/usr/bin/env bash
#
# scripts/checks.sh [--full]
#
# The green bar for contrib-pipeline, defined once. CI runs `scripts/checks.sh`
# and the commit guard runs it too. Changing this script means updating the
# Commands section of CLAUDE.md in the same commit.
#
#   (no flag)  shell syntax of every tracked or new shell script, then
#              tests/smoke/units.sh. CI runs this same script (it sees
#              tracked files only).
#   --full     also tests/smoke/suite.sh, the stub suite. It copies the local
#              xerj pipeline clone (the xerj profile's REPO_DIR), so it runs
#              only on this machine and CI cannot run it. It takes minutes.
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

full=0
case "${1:-}" in
  --full) full=1 ;;
  "") ;;
  *) echo "usage: scripts/checks.sh [--full]" >&2; exit 2 ;;
esac

command -v python3 >/dev/null || { echo "checks.sh: python3 is not on PATH" >&2; exit 1; }

# bash -n takes ONE file per call: `bash -n a.sh b.sh` parses only a.sh.
echo "==> shell syntax"
while IFS= read -r f; do
  [ -f "$f" ] || continue
  case "$f" in
    *.sh) ;;
    *) head -n 1 "$f" | grep -qE '^#!.*\b(ba)?sh\b' || continue ;;
  esac
  bash -n "$f"
done < <(git ls-files --cached --others --exclude-standard -- scripts .claude/hooks tests tools contrib-one contrib-publish)

echo "==> tests/smoke/units.sh"
bash tests/smoke/units.sh

if [ "$full" -eq 1 ]; then
  echo "==> tests/smoke/suite.sh"
  bash tests/smoke/suite.sh
fi
echo "CHECKS PASS"
