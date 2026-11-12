# A learned profile: the rule format

Two sessions learn one repo. The first reads its bundle (the guide files, and the PRs outside
contributors got merged or had closed, with maintainers' comments) and drafts `rules.json`. The
second re-reads the bundle and the draft with fresh eyes, corrects it, and writes the final one.
Each rule says what a contribution to this repo has to look like, how strong it is, why, and
where the repo says so. The driver checks facts only: that each quote is really in the file or
the maintainer's comment it names, and that each PR is a merged PR it fetched. What a rule says
and how strong it is are your judgement, and your user approves the result before any run uses
it.

## rules.json

```json
{
  "summary": "Two to six short lines: what this project cares about most in a contribution.",
  "rules": [
    {
      "id": "fail-first-test",
      "section": "tests",
      "strength": "required",
      "text": "A fix comes with a test that fails before the change and passes after it.",
      "why": "CONTRIBUTING.md says a fix without a failing test will not be merged, and maintainers asked for one on two PRs.",
      "sources": [
        {"guide": "CONTRIBUTING.md", "quote": "every bug fix must include a regression test that fails without the fix"},
        {"pr": 2938, "comment": "rc-1234567", "quote": "please add a test that fails on main before this change"}
      ]
    },
    {
      "id": "conventional-subject",
      "section": "commits",
      "strength": "practice",
      "text": "Commit subjects use a conventional prefix with a scope, like fix(api): ...",
      "why": "Most merged PRs do it; no guide asks for it.",
      "sources": [{"prs": [2938, 2912, 2883, 2894, 2901]}]
    }
  ],
  "review": ["made fail-first-test required: CONTRIBUTING.md says a fix without one will not be merged"]
}
```

- **id**: lowercase letters, digits and hyphens, starting with a letter or digit, at most 40,
  unique.
- **section**: one of `scope`, `tests`, `checks`, `changelog`, `commits`, `pr-body`, `review`,
  `reference`, `ai-policy`, `legal`, `candidate-sources`, `for-you`. Use `candidate-sources`
  for where work to pick up is listed (labels, issue-less gap lists such as a ratchet or skip
  file). Use `for-you` for what only your user can do, by hand and once: sign a CLA, ask to be
  assigned to an issue, link an account. Sessions never see that section; your user does.
- **text**: the rule as an outcome a reviewer can check, in one or two plain sentences of at
  least 3 words and at most 300 characters: "`cargo fmt --check` passes", not "run cargo fmt".
- **strength**:
  - `required`: this project sends a PR back for breaking it. A guide states it as a
    requirement (must, never, do not, will not be merged), or maintainers asked for it on more
    than one PR. Advice ("please", "should", "prefer", "consider") is a practice, even in a
    guide, and so is anything only merged PRs show. The same holds in `for-you`.
  - `practice`: what merged PRs here usually do, or what a guide recommends.
- **why**: one or two sentences, at least 3 words and at most 300 characters, saying why the
  rule has this strength, in terms of its sources. Your user reads it to decide whether to
  trust the rule.
- **sources**: 1 to 12, each one of:
  - `{"guide": PATH, "quote": TEXT}`: PATH exactly as listed in the bundle's `guides/`.
  - `{"pr": NUMBER, "comment": ID, "quote": TEXT}`: a comment in that PR, by its `id`, written
    by an OWNER, MEMBER or COLLABORATOR (the driver checks GitHub's own label).
  - `{"prs": [NUMBER, ...]}`: up to 200 merged PRs in the bundle, each one actually doing what
    the rule says (read its files and body; do not list a PR you did not check).
- **review**: written by the review session only: one line per change it made to the draft,
  and why.

**Quotes** are copied from the source: one contiguous run of at least 8 words, at most 600
characters, starting and ending on whole words. Case, emphasis and code marks (`*`, `_`,
backticks), link targets, curly quotes, dash kinds and line breaks do not matter; everything
else does, so keep a quote inside one sentence or paragraph. In a comment, quote the
maintainer's own words, not text they quote from someone else or a suggested change.

The driver leaves out a source that does not check out and a rule with none that does, keeps
at most 60 rules (the first 60), refuses the whole file when it lists more than 120, and shows
your user what it left out and why.

## What to write rules about

- What maintainers ask for, again and again, in review: these are the rules guides often
  leave out.
- Why maintainers closed PRs without merging: write the rule that would have avoided it.
- The shape of the merged PRs outside contributors wrote: tests, changelog entries, commit
  subjects, PR body sections and length, what they leave out.
- Rules a guide states, even ones no PR shows yet.

Leave out:
- Anything the pipeline already does or never does: pushing, posting, commenting, filing
  issues. What only your user can do (signing, account setup, asking to be assigned) goes in
  `for-you` instead.
- Anything that would have a session handle secrets or credentials, send anything anywhere,
  or depend on details of one machine.
- Rules only one PR shows, and style a formatter or linter already enforces (name the check
  instead).
- Rules that need a fact outside the bundle. Write fewer rules rather than guess.

## Precedence

Sessions read, in order: the pipeline's rules, which a profile can never loosen; your user's
overrides for this repo; then required rules; then practices. A learned rule that conflicts
with a higher one is still worth writing; the session that meets the conflict names it as a
decision for your user.
