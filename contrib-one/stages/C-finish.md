# Stage C: review and finish

Get an independent review, act on it, and write the PR body.

## Checklist
1. **Review.** Spawn one `Agent` with `subagent_type` `code-reviewer` (pre-approved). Brief
   it with: the repo, the branch, the base SHA, the command to see the diff
   (`git diff <base>..HEAD`), the reference behaviour, and the standing rules it must apply
   (no em dashes, no attribution, the repo's review protocol). Do not give it your
   conclusions. Ask for findings by severity with confidence. Save its report, unedited, as
   `session/evidence/review.md`; the driver checks that it is there.
2. **Act on the findings.** Verify each one yourself. Fix the confirmed ones in new commits
   (never amend), with a test where a test can show it. Re-run what the fix touches through
   the driver. Note findings you judge not worth fixing, with the reason.
3. **Final runs on HEAD.** Ask for the new tests, the touched files' tests, `fmt`, `clippy`,
   and (for engine or API changes) `yaml` full. Every one must be `met: true` on the final
   commit. Copy the decisive logs into `session/evidence/`.
4. **PR body.** Write `session/PR_BODY.md` in the profile's shape. Then trim it: cut every sentence
   that repeats another, every filler phrase, every claim without evidence. Target the
   profile's word range. Check: no em or en dashes, no attribution, every number traceable
   to `session/evidence/`.
5. **Finish the packet.** Section 8 (review), final status line in the header (ready for
   review, with the final SHA), and make sure the two flowcharts are there.
6. **Overlap, one last time.** The driver refreshed `gh/` just before this stage. Read
   `gh/prs.json` (and any `gh/search-*.json`) for an open PR that is not the user's and
   touches the same behaviour, issue or ratchet line. If one appeared since stage A, stop
   with `needs-you` and name it; do not finish a duplicate.
7. Leave the worktree clean: everything committed.

End with `stage-done` and a one-line summary the queue can show. The driver then checks the
files mechanically; if it finds problems it starts this stage again with the list.
