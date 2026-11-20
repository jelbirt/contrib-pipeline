# Stage A: investigate

Decide whether this candidate is real, still free, and worth a PR, and pick the approach.
You may write tests in this stage, but not the fix.

## Checklist
The scout's `why` and any fix it suggests are a hypothesis from a short look, not a finding:
confirm them from the code before relying on them. When state.json's `candidate` has a
`probe`, the scout's test (its `test`) failed on the base as a new file at its `path` (log at
its `log`): start from that test, and check that it still fails in your clone, for that reason.
When `candidate.lead` is true, the user handed this bug over directly with `--lead`: their
`why` is the starting point and is verified the same way. If the code does not bear it out,
ask them (`needs-you`) rather than abandoning their lead. A lead has no `search_terms`:
take them from its `why` for the closed issue and PR searches in step 1.

1. **Recheck the claim and overlap** from `gh/` (fresh snapshot for this candidate): the
   issue's own file in `gh/issues/` for a new claim or assignee (no file: the issue is older
   than the snapshot reaches, so ask for `gh issue view <n> --comments` and `gh api
   repos/<repo>/issues/<n>/timeline --paginate` reads), then `gh/prs.txt` and a Grep
   of `gh/prs/` for the files you expect to change. Read every open PR whose files or title
   touch the same area. Any overlap: `abandon`. Then check that maintainers have not
   declined this change before: read the `## Linked from` list in the issue's file (or the
   timeline read), and the comments and reviews of every closed, unmerged PR and not-planned
   issue on it (`gh pr view <n> --comments` shows both; `gh issue view <n> --comments`). An
   issue-less candidate gets `gh search issues` and `gh search prs` reads with `--state
   closed` and its terms instead. A maintainer who declined it, deferred it to a later
   release, or called the behaviour expected: `abandon`, quoting them, unless something
   material changed since. A PR its author left, one a stale bot closed, or one turned down
   only for how it made the change is not a decline.
2. **Find the code.** Read the paths the candidate names and their callers. Read
   `git log` for those files: if a maintainer chose the current behaviour on purpose, note the
   commit and weigh that.
3. **Pin the reference behaviour.** Settle what correct looks like: the docs, the issue, the
   tests that already pin nearby behaviour, and any reference the profile names (read it the
   way the profile says, approach only, never copy). Cite what you relied on in details.md.
   Those citations are for the user only unless the profile says otherwise.
4. **Reproduce.** Write the failing test first (the profile names the patterns), commit it
   alone on the branch, and ask the driver to run it with `"expect": "fail"`. Use a live
   check only where the profile offers one. A candidate that does not reproduce is
   abandoned, with the evidence (a lead: `needs-you` with the evidence instead, see above).
5. **Weigh approaches.** List two or three ways to fix it. For each: what changes, risk,
   cost on the hot path, how it matches the reference. Then spawn one `Agent` (the
   general-purpose type) as an independent critic: give it the problem, the code pointers
   and the approaches, not your preference, and ask which it would pick and what each
   misses. This is pre-approved. Record its answer.
6. **Decide scope.** The smallest change that matches the reference fully for the reported
   case and its direct siblings. If the right fix is larger than the profile allows, or
   changes behaviour a maintainer chose on purpose, end with `needs-you`.
7. **Write the packet** (`session/packet.md`, stage A's part, as the packet rules above
   describe), start `session/details.md` with the source, base SHA, reference
   citations, the reproduction result and the critic's full answer, and write
   `session/plan.md`: the approach, the files, the tests, and what is out of scope.

End with `stage-done` once the failing test is recorded (`met: true` with expect fail) and the
packet and plan are written.
