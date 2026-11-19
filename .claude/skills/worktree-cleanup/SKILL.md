---
name: worktree-cleanup
description: Tear down finished git worktrees in the contrib-pipeline repo safely - verify each branch is merged and its tree is clean, then remove the worktree, delete the branch, and prune. Sweeps every merged-and-clean worktree at once, or targets one branch. Use when the user wants to clean up, tear down, close out, or remove a worktree or workstream in this repo, says "worktree cleanup", "sweep merged worktrees", "remove finished worktrees", or asks to delete a finished branch's directory.
---

# worktree-cleanup (contrib-pipeline)

A thin wrapper over this repo's [`scripts/rm-worktree.sh`](../../../scripts/rm-worktree.sh).
That script owns every gate (merged, clean tree, not the main checkout, not the
current directory), so this skill only decides *which* worktrees to hand it, and
confirms once.

Nothing gitignored in a worktree here holds work (only `__pycache__/`), so a
clean `git status` means there is nothing to lose. A pipeline run started from a
worktree wrote the shared `~/contrib-queue` and `~/contrib-work`, which teardown
does not touch.

## With a branch argument

```bash
scripts/rm-worktree.sh {branch}
```

If it refuses because the branch is not detectably merged, **do not reach for
`--force` reflexively**: it removes the only check between you and deleting
unmerged work. Confirm the merge first, with the PR's merge state on GitHub or
`git log origin/main --oneline`. The script checks both local `main` and
`origin/main`, so a refusal means neither contains the branch; a squash merge is
the usual innocent explanation.

Add `--delete-remote` when the remote branch should go too.

## With no argument: sweep

1. `git worktree list --porcelain` for candidates.
2. For each worktree that is not the main checkout, check that
   `git -C {dir} status --porcelain` is empty and that the branch is merged.
   Use the same fully qualified refs `rm-worktree.sh` uses (a bare name lets a
   same-named *tag* win, and checking only local `main` reports PR-merged
   branches as unmerged):

   ```bash
   git merge-base --is-ancestor "refs/heads/{branch}" "refs/heads/main" ||
   git merge-base --is-ancestor "refs/heads/{branch}" "refs/remotes/origin/main"
   ```
3. Print the merged-and-clean list and the ones being skipped, with why.
4. **Confirm once** for the whole batch.
5. Run `scripts/rm-worktree.sh {branch}` for each.
6. If the main checkout is behind `origin/main`, say so: it is what pipeline
   runs read, so it should be pulled. The commit guard blocks a pull on `main`,
   and a run reads that checkout mid-run, so pull only when no run holds the
   ledger lock:

   ```bash
   flock -n ~/contrib-queue/.run.lock true &&
     ALLOW_MAIN_COMMIT=1 git -C ~/contrib-pipeline pull --ff-only
   ```
