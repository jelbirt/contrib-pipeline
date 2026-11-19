# Stage: scout

Find contribution candidates in the repo and rank them. Research only: you change no code.

## Inputs (in your folder)
- `gh/issues.txt`, `gh/prs.txt`, `gh/mine.txt`: open issues, open PRs (with their files),
  and the user's own recent PRs, one line each. Snapshots taken by the driver just now.
  Read `gh/issues.txt` whole: it lists every issue in the snapshot, not a sample (its top
  lines say when gh's limit left older ones out).
- `gh/issues/<number>.md` and `gh/prs/<number>.md`: one issue with its body, every comment
  and a `## Linked from` list (the issues and PRs here that mention it, with their state and
  labels), or one PR with its body and every changed file. Read them for the issues you
  shortlist and the PRs that may overlap. To find the open PRs that change a file, Grep
  `gh/prs/` for its path, with `[` and `(` escaped (the pattern is a regex). (`gh/*.json`
  hold the same data on one very long line each; use the text files.)
- `known.txt`: slugs already in the ledger (worked, stopped, published). Skip them.
- `rejects.md`: past rejects. Do not bring one back unless something material changed, and
  say what.
- The clone: read code at the base with `git -C <clone> show <remote>/<branch>:<path>`, and
  history with `git -C <clone> log`. Never check out or modify the clone.

If you need a read the snapshots do not have (one issue's full comments, a PR's diff), ask
the driver with a `gh` request and end your turn.

## Sources, in order of preference
1. Open issues with a clear, reproducible defect and no claim.
2. Issue-less fixes the profile allows (a list of known gaps it names, or the kind of small
   fix it says needs no issue). **At most one issue-less candidate per run**, and only if you
   can name the user-visible failure it causes.

When your prompt says the run takes issue-less fixes only, skip source 1. Before you list a
fix, search `gh/issues.txt` and Grep `gh/issues/` for the behaviour it changes: a fix for a
defect an open issue already reports belongs to that issue, so drop it rather than list it
without the issue. If `gh/issues.txt` says gh's limit was reached, older issues are not in
the snapshot: ask for a `gh search issues` read with the fix's terms before you list it. Set
`"issue": null`, write a `source` such as `gap: <what>` with no issue or PR number or link in
it (the driver drops a candidate whose source cites one), and give one candidate at most.

### Finding an issue-less fix
No issue points at it, and you cannot run code, so find it by reading. Work these leads at
the base, in the paths the profile's scope allows (if it names none, the repo's main source
and test folders), leaving out any your prompt says the final gate refuses:
1. **What a recent fix missed.** List the recent fixes (`git -C <clone> log <remote>/<branch>
   --no-merges -n 200 --format='%h %ad %s' --date=short -- <paths>`), and read the diff of
   each one that fixes wrong behaviour (`git -C <clone> show <sha>`). A fix often repairs one
   path and leaves its twin: the same check missing in a sibling function or another type it
   handles, the other direction (read and write, encode and decode), another mode or option,
   or a second copy of the same logic. Find the twin and read at the base that it still has
   the same flaw. Before you keep a twin, ask for the fix's own PR thread (`gh pr view <n>
   --comments`, with the number from its subject, or a `gh search prs` read) and drop the twin
   if a maintainer left it out on purpose. Keep that number out of `source`.
2. **Code that contradicts its own word.** A docstring, error message, type annotation or
   docs page that promises one result while the code it describes gives another. Keep it
   only when the code is the wrong side (other docs, tests or callers agree with the
   promise): a change to the words alone has no test that fails before.
3. **Known-bug markers.** Tests marked as expected to fail, or skipped with a reason that
   names wrong behaviour, and TODO or FIXME comments that name a wrong result. Search the
   base, not the clone's checkout, which is older (`git -C <clone> grep -n -E '<pattern>'
   <remote>/<branch> -- <paths>`). Skip ones that wait on a design decision or a later
   release.

For a lead you keep, name the input that triggers it, the wrong result, and the lines at the
base that cause it. Say in `why` that the failure is read from the code, not run; stage A
reproduces it before any fix. In a run that takes issue-less fixes only, one module read is
not a search: work through at least the last 20 fix commits in scope (or all of them if
there are fewer) and a marker search before you answer with an empty list, and say in
`next.json`'s summary how many leads you checked.

## Every candidate must pass all of these (drop it otherwise)
- **Unclaimed:** no "I'll take this" in the last 14 days, no assignee other than the
  contributor named in your prompt, no linked open PR.
- **No overlap:** no open PR in `gh/prs.txt` touches the same behaviour. Compare by topic,
  not only by issue link: read the titles and bodies of every open PR that changes one of
  the files your fix would change, and of every PR whose title names the same endpoint,
  parameter or test file. A listed gap that an open PR closes is taken.
- **Not owner-only:** no roadmap epic, release work, or "maintainers will handle" label.
- **Fits the profile's scope:** a fix one PR can carry, with a test that fails before.
- **Not already fixed on the base:** check the code at the base, not only the issue text.
- **Not declined before:** maintainers have not already turned this change down or put it
  off. For an issue, read its `## Linked from` list. Every closed, unmerged PR and every
  issue closed as not planned on it may hold their answer: ask for its comments and reviews
  (`gh pr view <n> --comments` shows both; `gh issue view <n> --comments`), and read a label
  such as `deferred` or `wontfix` as an answer. For an issue-less fix, ask for `gh search
  issues` and `gh search prs` reads with `--state closed` and the fix's terms, and read what
  they find the same way. Drop a candidate, quoting the maintainer in `why`, when a
  maintainer declined it, deferred it to a later release, or called the behaviour expected,
  unless something material changed since; then say what. A PR its author left, one a stale
  bot closed, or one turned down only for how it made the change is not a decline: keep the
  candidate and say so in `why`.

## Output
Write `candidates.json`: a list, best first, at most 5, each:

```json
{"slug": "short-kebab-name", "title": "one line", "source": "issue #N | gap: <what the profile lists>",
 "issue": 123, "why": "two sentences: what is wrong, likely fix",
 "files": ["paths the fix likely touches"], "overlap_checked": ["#PR numbers you read"],
 "size": "S|M", "confidence": "high|medium",
 "search_terms": ["1 to 3 short phrases another PR fixing this would likely use in its title"]}
```

When your prompt says work on an issue starts only once the issue is assigned to the
contributor, add `"assign_comment"` to every issue candidate that is not assigned to them yet:
the comment the user would post to ask for it, in their voice, two to four sentences, saying
what is wrong and the fix they propose, following the profile on tone and any disclosure. No
attribution, no em dashes. The driver stops that candidate there and shows the user the draft.

An empty list is a valid answer: it means no good candidate, and the run stops cleanly.
Then write `next.json` with `{"action": "stage-done", "summary": "N candidates"}` (in a run that
takes issue-less fixes only, add the leads checked: `"0 candidates; 23 leads checked"`).
