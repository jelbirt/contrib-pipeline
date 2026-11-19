#!/usr/bin/env bash
#
# rm-worktree.sh {branch} [--force] [--delete-remote]
#
# Teardown mirror of new-worktree.sh. Gates before removing anything: a worktree
# exists at that branch and its directory is present, it is not the main
# checkout, you are not standing inside it, its tree is clean, and the branch is
# merged into the default branch (locally or on origin).
#
#   --force          also accept a branch git cannot see as merged (usually a
#                    squash merge).
#   --delete-remote  also delete origin/{branch} after a successful teardown.
#
# Nothing gitignored in a worktree here holds work (only __pycache__/), so a
# clean `git status` means there is nothing to lose.
#
# ORDER MATTERS, AND SO DOES WHO DECIDES. The worktree must be removed before
# the branch, because git will not delete a branch that is still checked out.
# That makes the removal irreversible by the time the branch delete runs, so
# nothing after it may veto: we use `git branch -D` and let the merged gate
# above be the sole authority. `git branch -d` asks a DIFFERENT question:
# reachable from HEAD or upstream, not "merged into the default branch", and
# when the two disagree it refuses after the worktree is already gone, leaving
# a half-torn-down repo.
#
set -euo pipefail

# Snapshot the caller's cwd BEFORE cd'ing, or the "not the directory you are
# standing in" gate silently compares the repo root against itself.
INVOKED_FROM="$(pwd -P 2>/dev/null || printf '%s' "${PWD:-}")"
# The LOGICAL cwd, unresolved. Must be captured here too: read at the gate it
# would already be REPO_ROOT, so the check would test the REPO ROOT against the
# worktree path, never the caller's directory. That is the shape this gate
# shipped in once: it reads as a second comparison and is a duplicate of the
# third loop entry.
INVOKED_LOGICAL="${PWD:-$INVOKED_FROM}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BRANCH=""
FORCE=0
DELETE_REMOTE=0
for arg in "$@"; do
  case "$arg" in
    --force)         FORCE=1 ;;
    --delete-remote) DELETE_REMOTE=1 ;;
    -*)              echo "rm-worktree.sh: unknown flag $arg" >&2; exit 1 ;;
    *)               if [ -n "$BRANCH" ]; then echo "rm-worktree.sh: extra argument $arg" >&2; exit 1; fi
                     BRANCH="$arg" ;;
  esac
done

if [ -z "$BRANCH" ]; then
  echo "usage: scripts/rm-worktree.sh {branch} [--force] [--delete-remote]" >&2
  exit 1
fi

cd "$REPO_ROOT"

DEFAULT_BRANCH=""
if git show-ref --verify --quiet refs/heads/main; then
  DEFAULT_BRANCH=main
elif head_ref="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)"; then
  DEFAULT_BRANCH="${head_ref#origin/}"
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "rm-worktree.sh: cannot determine the default branch, refusing to guess." >&2
  exit 1
fi

if [ "$BRANCH" = "$DEFAULT_BRANCH" ]; then
  echo "rm-worktree.sh: refusing to tear down the default branch ($DEFAULT_BRANCH)." >&2
  exit 1
fi

WT_DIR="$(git worktree list --porcelain \
  | awk -v b="refs/heads/$BRANCH" '
      /^worktree /   { dir = substr($0, 10) }
      /^branch /     { if (substr($0, 8) == b) { print dir; exit } }
  ')"

if [ -z "$WT_DIR" ]; then
  echo "rm-worktree.sh: no worktree is checked out at branch '$BRANCH'." >&2
  echo "                (see: git worktree list)" >&2
  exit 1
fi

# A registered worktree whose directory is gone is 'prunable'. Every check below
# would fail open on it, so stop here rather than deleting a branch whose real
# checkout may have simply been moved.
if [ ! -d "$WT_DIR" ]; then
  echo "rm-worktree.sh: worktree for '$BRANCH' is registered at" >&2
  echo "                $WT_DIR" >&2
  echo "                but that directory does not exist. If it was moved, use" >&2
  echo "                'git worktree repair'; if it is gone, 'git worktree prune'." >&2
  exit 1
fi

# No `head`: it exits after one line, and under pipefail the producer's SIGPIPE
# would abort this assignment under set -e with no message at all.
MAIN_CHECKOUT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
if [ "$WT_DIR" = "$MAIN_CHECKOUT" ]; then
  echo "rm-worktree.sh: '$BRANCH' is checked out in the MAIN checkout ($WT_DIR); refusing." >&2
  exit 1
fi

# Check the caller's cwd AND the repo root. Removing the directory a session is
# standing in leaves every later command failing on a deleted cwd.
# Compare BOTH forms of the cwd against BOTH forms of the worktree path. Each
# pairing catches a case the other misses:
#   - an ancestor symlink on the worktree path defeats a comparison against
#     the literal $WT_DIR, which is what WT_REAL is for;
#   - a shared directory symlinked INTO the worktree resolves back OUT of it,
#     so the PHYSICAL cwd lands outside and only INVOKED_LOGICAL still matches.
#     Teardown does NOT delete that directory (it removes the symlink and never
#     follows it), but $PWD is left naming a path inside a worktree that no
#     longer exists, and the gate's contract is that you are not standing in it.
WT_REAL="$(cd "$WT_DIR" 2>/dev/null && pwd -P || printf '%s' "$WT_DIR")"
for d in "$INVOKED_FROM" "$INVOKED_LOGICAL" "$REPO_ROOT"; do
  case "$d" in
    "$WT_DIR"|"$WT_DIR"/*|"$WT_REAL"|"$WT_REAL"/*)
      echo "rm-worktree.sh: you are standing inside $WT_DIR; cd out first." >&2
      exit 1 ;;
  esac
done

# Gate: clean tree. Capture the status and its EXIT CODE separately: a command
# substitution inside `[ ]` discards the exit code, so a failing `git status`
# would read as "clean" and skip the gate.
if ! WT_STATUS="$(git -C "$WT_DIR" status --porcelain 2>&1)"; then
  echo "rm-worktree.sh: cannot read the status of $WT_DIR; refusing." >&2
  printf '%s\n' "$WT_STATUS" >&2
  exit 1
fi
if [ -n "$WT_STATUS" ]; then
  echo "rm-worktree.sh: $WT_DIR has uncommitted changes; refusing." >&2
  printf '%s\n' "$WT_STATUS" >&2
  exit 1
fi

# Gate: merged. Use fully-qualified refs: a bare name lets a same-named TAG win
# the lookup and make an unmerged branch look merged. Check origin too: in this
# repo's own flow the branch is merged by a PR on GitHub, so local main is
# usually behind and a local-only test sends people to --force by habit.
git fetch --quiet origin "$DEFAULT_BRANCH" 2>/dev/null || true
merged=0
for base in "refs/heads/$DEFAULT_BRANCH" "refs/remotes/origin/$DEFAULT_BRANCH"; do
  git show-ref --verify --quiet "$base" || continue
  if git merge-base --is-ancestor "refs/heads/$BRANCH" "$base"; then
    merged=1
    break
  fi
done
if [ "$merged" -eq 0 ]; then
  if [ "$FORCE" -eq 0 ]; then
    echo "rm-worktree.sh: '$BRANCH' is not merged into $DEFAULT_BRANCH (local or origin)." >&2
    echo "                Refusing. If it was squash-merged, re-run with --force." >&2
    exit 1
  fi
  echo "==> '$BRANCH' not detectably merged; proceeding because --force was given"
fi

echo "==> git worktree remove $WT_DIR"
if ! rm_err="$(git worktree remove "$WT_DIR" 2>&1)"; then
  # The clean-tree gate above already passed, so what remains should be only the
  # gitignored state Python created (__pycache__/).
  # Show git's actual reason rather than asserting one.
  echo "    git declined:" >&2
  printf '%s\n' "$rm_err" | sed 's/^/      /' >&2
  echo "    retrying with --force (tracked tree was verified clean above)" >&2
  git worktree remove --force "$WT_DIR"
fi

# -D, not -d: see the header. The merged gate above is the authority, and
# nothing may veto after the worktree is already gone.
echo "==> git branch -D $BRANCH"
git branch -D "$BRANCH"

echo "==> git worktree prune"
git worktree prune

REMOTE_FAILED=0
if [ "$DELETE_REMOTE" -eq 1 ]; then
  echo "==> git push origin --delete $BRANCH"
  # Non-fatal: every local step is already done and is NOT retryable (a re-run
  # exits early, the worktree and branch being gone). Aborting here under set -e
  # would report a failed teardown that in fact fully succeeded.
  git push origin --delete "$BRANCH" || {
    REMOTE_FAILED=1
    echo "    local teardown COMPLETED; only the remote delete failed. Retry with:" >&2
    echo "      git push origin --delete $BRANCH" >&2
  }
fi

if [ "$REMOTE_FAILED" -eq 1 ]; then
  echo "==> torn down: $BRANCH (remote branch still present)"
else
  echo "==> torn down: $BRANCH"
fi
