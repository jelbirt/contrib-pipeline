# contrib-pipeline

## How changes land

- Every change goes through a pull request into `main`. Nothing is committed straight to
  `main`.
- Do branch work in its own worktree, never by switching this checkout's branch (see below):
  `git fetch origin && git worktree add ../contrib-pipeline-<topic> -b <topic> origin/main`.
  Remove the worktree with `git worktree remove` once its PR merges.
- One concern per branch. Unrelated changes get their own branch and PR.
- Before the PR goes up, run one code-review pass over the full branch diff.
- The owner reviews and merges; a session never merges. A session pushes a branch or opens a
  PR only on the owner's go. An approved plan that names the PR counts as that go.

## This checkout stays on `main`

`~/.claude/skills/contrib-one` and `~/.claude/skills/contrib-publish` are symlinks into this
checkout, and the driver reads its rules and stage prompts from here each time a session
starts. Whatever is checked out here is what a pipeline run uses, even partway through a run.
Keep it on `main`. Once a PR merges, pull `main` here: the owner, or the next session that
finds `main` behind `origin/main`. If this checkout must switch anyway, first check that no
run holds the ledger lock: `flock -n ~/contrib-queue/.run.lock true` succeeds only when none
does.

## Checks before every commit

- `bash tests/smoke/units.sh` prints `UNITS PASS`.
- `bash tests/smoke/suite.sh` prints `SUITE PASS`. It takes a few minutes, so run it in the
  background.
- CI (`.github/workflows/tests.yml`) runs `units.sh` only, so the stub suite is checked
  locally and nowhere else.
