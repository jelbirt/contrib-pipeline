# Stage: scout

Find contribution candidates in the repo and rank them. Research only: you change no code.

## Inputs (in your folder)
- `gh/issues.json`, `gh/prs.json`, `gh/mine.json`: open issues, open PRs (with their files),
  and the user's own recent PRs. Snapshots taken by the driver just now.
- `known.txt`: slugs already in the ledger (worked, stopped, published). Skip them.
- `rejects.md`: past rejects. Do not bring one back unless something material changed, and
  say what.
- The clone: read code at the base with `git -C <clone> show <remote>/<branch>:<path>`, and
  history with `git -C <clone> log`. Never check out or modify the clone.

If you need a read the snapshots do not have (one issue's full comments, a PR's diff), ask
the driver with a `gh` request and end your turn.

## Sources, in order of preference
1. Open issues with a clear, reproducible defect and no claim.
2. Issue-less gaps the profile names (for XERJ: lines in `catch-lenient.txt`, the ratchet of
   known ES-YAML gaps). **At most one issue-less candidate per run**, and only if you can
   name the user-visible failure it causes.

## Every candidate must pass all of these (drop it otherwise)
- **Unclaimed:** no "I'll take this" or assignee in the last 14 days, no linked open PR.
- **No overlap:** no open PR in `gh/prs.json` touches the same behaviour. Compare by topic,
  not only by issue link: read the titles and bodies of every open PR whose `files` include
  the files your fix would change, and of every PR whose title names the same endpoint,
  parameter or test file. A ratchet line that an open PR deletes is taken.
- **Not owner-only:** no roadmap epic, release work, or "maintainers will handle" label.
- **Fits the profile's scope:** a fix one PR can carry, with a test that fails before.
- **Not already fixed on the base:** check the code at the base, not only the issue text.

## Output
Write `candidates.json`: a list, best first, at most 5, each:

```json
{"slug": "short-kebab-name", "title": "one line", "source": "issue #N | catch-lenient: <line>",
 "issue": 123, "why": "two sentences: what is wrong, likely fix",
 "files": ["paths the fix likely touches"], "overlap_checked": ["#PR numbers you read"],
 "size": "S|M", "confidence": "high|medium",
 "search_terms": ["1 to 3 short phrases another PR fixing this would likely use in its title"]}
```

An empty list is a valid answer: it means no good candidate, and the run stops cleanly.
Then write `next.json` with `{"action": "stage-done", "summary": "N candidates"}`.
