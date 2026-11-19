# CLAUDE.md: contrib-pipeline

How agent sessions work in this repo. What the pipeline is and how to run it
lives in [`README.md`](README.md), [`SPEC.md`](SPEC.md) and
[`contrib-one/SKILL.md`](contrib-one/SKILL.md); its design history in
[`contrib-one/DESIGN.md`](contrib-one/DESIGN.md). This file restates none of it.

## Commands

The green bar is defined once, in [`scripts/checks.sh`](scripts/checks.sh):

```bash
scripts/checks.sh          # shell syntax, then tests/smoke/units.sh (about 40 s)
scripts/checks.sh --full   # also tests/smoke/suite.sh, the stub suite (minutes)
```

CI runs `scripts/checks.sh` and adds nothing of its own. The stub suite is the
one check CI cannot run: it copies the local xerj pipeline clone (the xerj
profile's `REPO_DIR`). So `--full` is the real bar before every commit, and
local green covers more than CI green. Changing the bar means editing
`checks.sh` and this section in the same commit.

## Green before every commit, and `main` is the review inbox

`scripts/checks.sh` passes before each commit, and work lands on `main` only by
PR. [`.claude/hooks/pre-commit-guard.sh`](.claude/hooks/pre-commit-guard.sh)
enforces both at the tool call: it runs `scripts/checks.sh` (not `--full`)
before a `git commit`, and blocks `commit`, `merge`, `pull`, `cherry-pick`,
`revert`, `am` and `rebase` on `main`. Escapes, typed into the command so they
show in the transcript:

| Escape | Effect |
|---|---|
| `SKIP_CHECKS=1 git commit ...` | commit without running the bar |
| `ALLOW_MAIN_COMMIT=1 git commit ...` | commit directly on `main` |
| `ALLOW_MAIN_COMMIT=1 git pull --ff-only` | any other blocked verb on `main`, such as the pull after a PR merges |

The guard is a guardrail for cooperating sessions, not a security boundary, and
it is feature-frozen: fix it only if it blocks legitimate work. It parses the
command with `node`; with no `node` on PATH it allows everything. It does not see
`gh pr merge`; PRs are merged by the owner, never by an agent. Pipeline
sessions load no project settings (`SETTING_SOURCES` in `contrib-run`), so the
guard never touches a run.

## Parallel workstreams

One branch per workstream, one worktree each:
[`scripts/new-worktree.sh`](scripts/new-worktree.sh) `{branch}` creates
`../contrib-pipeline-{branch}` from `origin/main`. Tear down with
[`scripts/rm-worktree.sh`](scripts/rm-worktree.sh) `{branch}` or the repo-local
`worktree-cleanup` skill.

**The main checkout stays on `main`.** `~/.claude/skills/contrib-one` and
`~/.claude/skills/contrib-publish` are symlinks into it, and the driver reads
its rules and stage prompts from there at every session start, so whatever is
checked out there is what a pipeline run uses, even partway through a run.
`~/xerj-drafts/tools/guarded.sh` links to its `tools/guarded.sh` too. Pull
`main` there after a PR merges, while no run holds the lock (see below):
`ALLOW_MAIN_COMMIT=1 git -C ~/contrib-pipeline pull --ff-only`.

## Shared state: who holds the pen

Worktrees isolate this repo's files, not what the pipeline writes:

- **`~/contrib-queue`**, the ledger: its own local git repo, no remote, private.
  One pipeline run at a time, enforced by the driver: `contrib-run` holds
  `~/contrib-queue/.run.lock` for the whole run. Check with
  `flock -n ~/contrib-queue/.run.lock true` (succeeds only when no run holds it).
  A run's own ledger commit stages everything (`git add -A`), so leave no stray
  files there; ask the owner before committing in the ledger by hand.
- **`~/contrib-work`**: clones, test envs and caches the runs write. Same pen.

The test commands touch neither: `units.sh` uses temp folders, `suite.sh` uses
`~/contrib-smoke/{stamp}`.

## Repo-specific invariants

- **The driver and stage prompts stay generic.** Facts about one upstream repo
  (its commands, paths, rules) live only in `contrib-one/profiles/`. Unit
  checks enforce part of this; ask the owner before adding anything repo-,
  language- or tool-specific to shared code.
- **Upstream builds and tests run only under the build guard**: through the
  driver (its bwrap jail runs inside `tools/guarded.sh`) or by hand through
  `tools/guarded.sh`. One heavy job at a time, with at least 32 GB free on C:.
- **Nothing reaches an upstream repo without the owner's go.** The pipeline
  never pushes or posts; publishing is `contrib-publish`, on the owner's
  "push and open". This is about upstream contributions, not this repo's PRs.
