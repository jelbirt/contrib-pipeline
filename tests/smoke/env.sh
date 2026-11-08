# Source this before the stub suites. Everything lives under $SMOKE (default ~/contrib-smoke),
# never in the real ledger or work dir.
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
SMOKE=${SMOKE:-$HOME/contrib-smoke}
export CONTRIB_LEDGER=$SMOKE/ledger CONTRIB_WORK=$SMOKE/work CONTRIB_PROFILE_DIR=$SMOKE/profiles \
       CONTRIB_TRANSCRIPTS=$SMOKE/tr STUB_LOG=$SMOKE/stub.log
mkdir -p "$CONTRIB_LEDGER" "$CONTRIB_WORK" "$CONTRIB_PROFILE_DIR" "$CONTRIB_TRANSCRIPTS"
cp "$ROOT"/contrib-one/profiles/* "$CONTRIB_PROFILE_DIR"/
if [ ! -d "$CONTRIB_LEDGER/.git" ]; then
  git -C "$CONTRIB_LEDGER" init -q -b main
  mkdir -p "$CONTRIB_LEDGER"/{candidates,runs,cache}; touch "$CONTRIB_LEDGER"/{QUEUE.md,rejects.md}
  printf 'cache/\ncandidates/*/bin/\ncandidates/*/node/\n*.lock\nSTOP\nSTOP-NOW\n' > "$CONTRIB_LEDGER/.gitignore"
  git -C "$CONTRIB_LEDGER" add -A && git -C "$CONTRIB_LEDGER" -c user.name=smoke -c user.email=smoke@localhost commit -qm "smoke ledger"
fi
R=$ROOT/contrib-one/bin/contrib-run
STUB=$ROOT/contrib-one/tests/stub-claude
