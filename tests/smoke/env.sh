# Source this before the stub suites. Everything lives under $SMOKE (default ~/contrib-smoke),
# never in the real ledger, work dir or pipeline clone.
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
# The driver clones each candidate from REPO_DIR and saves its branch back into it. The real
# REPO_DIR is the pipeline clone real runs use, so the suite gets its own copy and the copied
# profile points there. A local clone hard-links the object files; git never changes one in place
# (it writes new files and renames or deletes old ones), so nothing done to the copy changes what
# the real clone holds. While both hold the same packs the copy costs almost no disk; once the
# real clone repacks, the copy alone holds the old ones, so suite.sh deletes it when it passes.
PROFILE=$CONTRIB_PROFILE_DIR/xerj-org-xerj.env
REAL_REPO=$(sed -n 's/^REPO_DIR=\([^[:space:]]*\).*/\1/p' "$ROOT/contrib-one/profiles/xerj-org-xerj.env")
SMOKE_REPO=$SMOKE/repo
case $SMOKE_REPO in *[!A-Za-z0-9/._-]*)
  echo "refusing: $SMOKE has characters the profile rewrite cannot carry"; return 2;; esac
if [ ! -d "$SMOKE_REPO" ]; then
  # The real clone's layout: not bare (repo_gc skips a bare repository) and a detached HEAD (a
  # mirror turns HEAD into a branch when some branch tip is the same commit, and a fetch into the
  # checked-out branch of a non-bare repository is refused).
  if [ -z "$REAL_REPO" ] || ! { git clone -q --mirror "$REAL_REPO" "$SMOKE_REPO/.git" &&
      git -C "$SMOKE_REPO" config core.bare false &&
      git -C "$SMOKE_REPO" update-ref --no-deref HEAD HEAD &&
      # Not `git remote remove`: on a mirror its refspec is refs/*, so that would delete every ref.
      git -C "$SMOKE_REPO" config --remove-section remote.origin &&
      git -C "$SMOKE_REPO" remote add upstream "$(git -C "$REAL_REPO" remote get-url upstream)" &&
      git -C "$SMOKE_REPO" remote set-url --push upstream no_push; }; then
    echo "could not copy the pipeline clone ($REAL_REPO) into $SMOKE_REPO"; rm -rf "$SMOKE_REPO"; return 2
  fi
fi
sed -i "s#^REPO_DIR=.*#REPO_DIR=$SMOKE_REPO   \# the suite's own copy (env.sh)#" "$PROFILE"
if ! grep -q "^REPO_DIR=$SMOKE_REPO " "$PROFILE"; then
  echo "refusing: $PROFILE does not point at the suite's copy"; return 2
fi
R=$ROOT/contrib-one/bin/contrib-run
STUB=$ROOT/contrib-one/tests/stub-claude
