# Stage C: review and finish

Get an independent review, act on it, and write the PR body.

## Checklist
1. **Review.** Spawn one `Agent` with `subagent_type` `code-reviewer` (pre-approved), in the
   foreground: do not set `run_in_background`, because the driver only counts a review whose
   report came back in that call, and wait for it before you change anything. Brief
   it with: the repo, the branch, the base SHA, the command to see the diff
   (`git diff <base>..HEAD`), the reference behaviour, and the standing rules it must apply
   (no em dashes, no attribution, the repo's review protocol). Do not give it your
   conclusions. Ask for findings by severity with confidence. Save its report, unedited, as
   `session/evidence/review.md`; the driver checks that it is there.
2. **Act on the findings.** Verify each one yourself. Fix the confirmed ones in new commits
   (never amend), with a test where a test can show it. Re-run what the fix touches through
   the driver. Note findings you judge not worth fixing, with the reason.
3. **Final runs on HEAD.** Ask for the new tests, the touched files' tests, and every format,
   lint and wider check the profile requires for this change. Every one must be `met: true`
   on the final commit. Copy the decisive logs into `session/evidence/`.
4. **PR body.** Write `session/PR_BODY.md` in the profile's shape. Then trim it: cut every sentence
   that repeats another, every filler phrase, every claim without evidence. Target the
   profile's word range. Check: no em or en dashes, no attribution, every number traceable
   to `session/evidence/`.
5. **Finish the packet.** Write Review (counts and what happened to each real finding;
   the full table goes in `session/details.md`), recheck Other open PRs nearby, fill every
   at-a-glance row, set the status line to `**Ready to publish.**`, and put the PR title,
   the PR body's word count, the branch and the final short SHA in the footer. Then reread
   it as the user will: a reader outside this area should understand the problem, the
   choice and each decision without opening `details.md`. Cut it to the word limit.
6. **Overlap, one last time.** The driver refreshed `gh/` just before this stage. Read
   `gh/prs.json` (and any `gh/search-*.json`) for an open PR that is not the user's and
   touches the same behaviour, issue or listed gap. If one appeared since stage A, stop
   with `needs-you` and name it; do not finish a duplicate.
7. Leave the worktree clean: everything committed.

End with `stage-done` and a one-line summary in plain words (the queue shows the packet's
title and status line, so the summary is for the run log). The driver then checks the
files mechanically; if it finds problems it starts this stage again with the list.
