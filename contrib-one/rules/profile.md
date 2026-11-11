# A learned profile: the rule format

A learn session reads one repo's bundle (its guide files, and the PRs outside contributors got
merged or had closed, with maintainers' comments) and writes `rules.json`: what a contribution
to this repo has to look like, each rule with its sources. The driver checks every source
against the same bundle, keeps what checks out, and renders the kept rules into the profile
that later sessions read. Your user reads a review of it before any run uses it.

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
      "sources": [{"prs": [2938, 2912, 2883, 2894, 2901]}]
    }
  ]
}
```

- **id**: lowercase letters, digits and hyphens, starting with a letter or digit, at most 40,
  unique.
- **section**: one of `scope`, `tests`, `checks`, `changelog`, `commits`, `pr-body`, `review`,
  `reference`, `ai-policy`, `legal`, `candidate-sources`. Use `candidate-sources` for where
  work to pick up is listed (labels, issue-less gap lists such as a ratchet or skip file).
- **text**: the rule as an outcome a reviewer can check, in one or two plain sentences of at
  least 3 words and at most 300 characters: "`cargo fmt --check` passes", not "run cargo fmt".
  No links, host names with a path, or e-mail addresses: the driver refuses a rule whose text
  has one (the sources carry the links).
- **strength** and **sources**:

| Strength | Sources that count |
|---|---|
| required | a quote from a guide file; or quotes from maintainers' comments on 2 or more different PRs |
| practice | a list of merged PRs that do it (at least 3, and at least half the merged PRs in the bundle); or one maintainer comment; or a guide quote |

A rule has 1 to 12 sources; with more, the whole rule is refused. A source is one of:
- `{"guide": PATH, "quote": TEXT}`: PATH exactly as listed in the bundle's `guides/`.
- `{"pr": NUMBER, "comment": ID, "quote": TEXT}`: a comment in that PR's `comments`, by its
  `id`, written by an OWNER, MEMBER or COLLABORATOR.
- `{"prs": [NUMBER, ...]}`: up to 200 merged PRs in the bundle, each one actually doing what
  the rule says (read its diff summary and body; do not list a PR you did not check). Each
  list is judged on its own: two lists of 2 do not make one of 4.

**Quotes** are copied from the source, one contiguous run of at least 8 words, at most 600
characters. The words are counted on the text a reader sees, so words inside a link target do
not count. Case, emphasis and code marks (`*`, `_`, backticks), link targets, curly quotes,
dash kinds and line breaks do not matter; everything else does, including `#`, list markers,
table pipes and HTML, so keep a quote inside one sentence or paragraph. Where the source has
a long dash, write a plain hyphen. In a comment, quote the maintainer's own words in one
paragraph: block quotes (and the lines that run on from them), code blocks, suggestion blocks,
HTML block quotes, details, pre blocks and inline quotes, and HTML comments are someone else's
or a proposal, and do not count. In a guide, everything counts, HTML comments too: maintainers
commit guides, and PR templates keep their guidance in comments. A quote starts and ends on
whole words.

The driver refuses a source that does not check out and keeps a rule only on the sources that
do. It makes a required rule a practice when no guide quote backs it and fewer than 2 PRs'
maintainers do (for example, when only merged-PR lists back it). It shows the quote as it
matched, without link targets. What it refused or changed, and why, is shown to your user.

## What to write rules about

- What maintainers ask for, again and again, in review: these are the rules guides often
  leave out.
- Why maintainers closed PRs without merging: write the rule that would have avoided it.
- The shape of the merged PRs outside contributors wrote: tests, changelog entries, commit
  subjects, PR body sections and length, what they leave out.
- Rules a guide states, even ones no PR shows yet.

Leave out:
- Anything the pipeline already does or never does: pushing, posting, commenting, filing
  issues, signing, account setup. A rule about secrets, posting or filing anything, or local
  machine details is dropped by the driver's screen.
- Rules only one PR shows, and style a formatter or linter already enforces (name the check
  instead).
- Rules that need a fact outside the bundle. Write fewer rules rather than guess.

## Precedence

Sessions read, in order: the pipeline's rules, which a profile can never loosen; your user's
overrides for this repo; then required rules; then practices. A learned rule that conflicts
with a higher one is still worth writing; the session that meets the conflict names it as a
decision for your user.
