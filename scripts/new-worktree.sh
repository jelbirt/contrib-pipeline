#!/usr/bin/env bash
#
# new-worktree.sh {branch} [dir]
#
# Create a worktree for one workstream of contrib-pipeline, cut from origin/main.
# Default dir: ../contrib-pipeline-{branch}.
#
# WHAT IS WIRED, AND WHY
#
#   Nothing is copied, shared or installed. The repo has no secrets file, no
#   dependencies and no build: the driver and its tests use only the Python
#   standard library, bash, bubblewrap and socat from this machine. Python
#   recreates __pycache__/ in each worktree.
#
# SHARED STATE: WHO HOLDS THE PEN
#
#   A worktree isolates this repo's files, not what the pipeline writes:
#
#     ~/contrib-queue  the ledger, its own local git repo with no remote. One
#                      pipeline run at a time: contrib-run holds
#                      ~/contrib-queue/.run.lock while it runs.
#     ~/contrib-work   the pipeline's clones, test envs and caches, written by
#                      runs.
#
#   contrib-one/bin/contrib-run started from a worktree writes those same
#   folders. The test commands do not: units.sh uses temp folders and suite.sh
#   uses ~/contrib-smoke/{stamp}.
#
#   Other places read the MAIN checkout, never a worktree:
#     ~/.claude/skills/contrib-one, ~/.claude/skills/contrib-publish
#         symlinks into the main checkout. Every pipeline session reads the
#         driver, rules and stage prompts from there, at each session start.
#     ~/xerj-drafts/tools/guarded.sh
#         a symlink to the main checkout's tools/guarded.sh.
#   That is why work happens here and the main checkout stays on main.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="${1:-}"
if [ -z "$BRANCH" ]; then
  echo "usage: scripts/new-worktree.sh {branch} [dir]" >&2
  exit 1
fi

# Resolve the default branch explicitly. Falling back to whatever is checked out
# would silently make the CURRENT branch "the default" and quietly change what
# new work is cut from.
DEFAULT_BRANCH=""
if git show-ref --verify --quiet refs/heads/main; then
  DEFAULT_BRANCH=main
elif head_ref="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)"; then
  DEFAULT_BRANCH="${head_ref#origin/}"
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "new-worktree.sh: cannot determine the default branch (no refs/heads/main," >&2
  echo "                 no origin/HEAD). Set one, or pass the base explicitly." >&2
  exit 1
fi

if [ "$BRANCH" = "$DEFAULT_BRANCH" ]; then
  echo "new-worktree.sh: '$BRANCH' is the default branch: it lives in the main checkout." >&2
  exit 1
fi

SLUG="$(printf '%s' "$BRANCH" | tr '/' '-' | tr -cd 'A-Za-z0-9._-')"
WT_DIR="${2:-$REPO_ROOT/../contrib-pipeline-$SLUG}"

# A sanity guard against shell metacharacters, not against spaces. Keep every
# expansion of WT_DIR in this script quoted.
case "$WT_DIR" in
  *[!-A-Za-z0-9._/+~@:,\ ]*)
    echo "new-worktree.sh: refusing dir '$WT_DIR': shell metacharacters are" >&2
    echo "                 refused as a safety guard." >&2
    exit 1 ;;
esac

if [ -e "$WT_DIR" ]; then
  echo "new-worktree.sh: $WT_DIR already exists; pick another dir or remove it first." >&2
  exit 1
fi

# --- Pick the base ----------------------------------------------------------
# Fetch, then branch from origin/DEFAULT_BRANCH when we have it: fetching and
# then branching from the stale LOCAL ref reads as protection while providing
# none.
git fetch --quiet origin "$DEFAULT_BRANCH" 2>/dev/null || true
BASE="$DEFAULT_BRANCH"
if git show-ref --verify --quiet "refs/remotes/origin/$DEFAULT_BRANCH"; then
  BASE="origin/$DEFAULT_BRANCH"
fi

# --- Create -----------------------------------------------------------------
# If anything below fails, `set -e` aborts with the worktree already created and
# the existence check above then blocks a retry. Undo it instead.
CREATED=""
BRANCH_CREATED=""
cleanup_on_fail() {
  local rc=$?
  [ "$rc" -eq 0 ] && return 0
  if [ -n "$CREATED" ]; then
    echo "new-worktree.sh: failed after creating $CREATED, undoing so you can retry." >&2
    git worktree remove --force "$CREATED" 2>/dev/null || true
    git worktree prune 2>/dev/null || true
    [ -n "$BRANCH_CREATED" ] && git branch -D "$BRANCH" 2>/dev/null || true
  fi
  return 0
}
trap cleanup_on_fail EXIT

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "==> reusing existing branch $BRANCH"
  git worktree add "$WT_DIR" "$BRANCH"
  FROM="existing branch, as it was"
else
  echo "==> creating branch $BRANCH from $BASE"
  git worktree add -b "$BRANCH" "$WT_DIR" "$BASE"
  BRANCH_CREATED=1
  FROM="from $BASE"
fi
CREATED="$WT_DIR"
WT_DIR="$(cd "$WT_DIR" && pwd)"
CREATED="$WT_DIR"

trap - EXIT

cat <<EOF

Worktree ready: $WT_DIR
  branch  $BRANCH  ($FROM)

Next:
  cd "$WT_DIR"
  scripts/checks.sh

Pen reminder: a pipeline run started from here writes the shared ledger
(~/contrib-queue) and work folder (~/contrib-work), one run at a time.
EOF
