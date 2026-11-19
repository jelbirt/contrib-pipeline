# Stage: scout

Find contribution candidates in the repo and rank them. Research only: you change no code.

## Inputs (in your folder)
- `gh/issues.txt`, `gh/prs.txt`, `gh/mine.txt`: open issues, open PRs (with their files),
  and the user's own recent PRs, one line each. Snapshots taken by the driver just now.
  Read `gh/issues.txt` whole: it lists every issue in the snapshot, not a sample (its top
  lines say when gh's limit left older ones out).
- `gh/issues/<number>.md` and `gh/prs/<number>.md`: one issue with its body and every
  comment, or one PR with its body and every changed file. Read them for the issues you
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
Then write `next.json` with `{"action": "stage-done", "summary": "N candidates"}`.
