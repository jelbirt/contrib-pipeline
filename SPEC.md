# SPEC: phase 1, the pipeline learns each repo's contribution rules

**Approved 2026-11-11, with both recommended decisions (see the end).**

## Objective

Today the pipeline knows how to contribute to one repo, xerj-org/xerj, because a 101-line
profile (`contrib-one/profiles/xerj-org-xerj.md`) was written by hand. Phase 1 replaces that
hand knowledge with a **learned profile**. The pipeline reads the repo's own guides and the
PRs outside contributors got merged (and the ones maintainers closed, with their reasons),
then writes the rules it found, with a **checked source for every rule**. It rechecks those
rules where they matter.

It is for you, reviewing a run's output: you should be able to trust that a packet and PR
body follow what this project accepts, and see at once when the project's rules changed.

**Done means:** a learned profile for xerj-org/xerj covers what the hand profile says (or
explains each gap), you approve it, and a real run on it produces a packet and PR body at
least as good as run 2's.

**Out of scope:** learning build and test commands (layer 2: the driver still runs cargo and
the XERJ node, so another repo can be learned but not yet worked end to end), setting up a
new repo's clone and `.env` automatically, and learning from how our own PRs were reviewed
(phase 3).

## How it works

```mermaid
flowchart LR
  L["Onboarding: --learn<br/>(Opus, once per repo)"] --> R{"You read<br/>PROFILE-REVIEW.md"}
  R -->|approve| P[("Learned profile:<br/>rules + sources")]
  P --> S["Each scout: driver checks<br/>guides and new PRs<br/>(model only if changed)"]
  S -->|changed| V["SUMMARY and QUEUE<br/>list every change"]
  P --> A["Stage A: past PRs<br/>in this code area"]
  P --> X["Stage C and publish:<br/>driver flags rules changed<br/>since the candidate began"]
```

The driver does all fetching with `gh` and git, at no model cost. A model reads only where
judgment is needed.

| Where | What happens | Added cost (API-equivalent) |
|---|---|---|
| Onboarding | Driver fetches the guide files at the base, up to 30 merged PRs by outside contributors with their reviews, up to 15 PRs maintainers closed unmerged with their comments, labels and recent commit subjects. One Opus session writes the profile. | about $1 to $4, once per repo |
| Each scout | Driver compares guide blob SHAs at the new base and counts outside PRs merged since the last learn. A Sonnet session reads only what changed. | $0 most runs; about $0.30 otherwise |
| Stage A | Driver adds `gh/area.json`: the last 8 merged PRs that touched the candidate's files, with maintainer review comments. Stage A reads it in its normal investigation. | about $0.20 to $0.60 per candidate |
| Stage C, publish | Driver compares the guides at the current base with the revision the candidate started under, and says what changed. No model. | $0 |

Usage here is subscription limits, not dollars, so `--max-budget-usd` would be ignored.
Learning sessions are capped with `--max-turns` and a wall-clock timeout instead, and their
cost is its own row in SUMMARY.md.

**What gets fetched, exactly.** Guides: a fixed list of paths (AGENTS.md, CLAUDE.md,
CONTRIBUTING*, CODE_OF_CONDUCT*, CLA*, `.contributors`, `.github/*TEMPLATE*`,
`.github/*CONTRIBUT*`, `.github/AI*`, `docs/*CONTRIBUT*`, `docs/*REVIEW*`, CODEOWNERS), files
those link to inside the repo, and any file a current rule cites; at most 40 files of 200 KB.
PRs: only authors outside OWNER, MEMBER and COLLABORATOR, no bots, none that only touch CLA
files, and none of yours (your preferences live in your overrides). The search API supplies
`author_association`; a commit maps to its PR through `commits/<sha>/pulls`, because XERJ's
`(#N)` subject suffixes are issue numbers. Each PR body is capped at 20 KB, each comment at
5 KB, the whole bundle at 3 MB.

## The learned profile

Each rule is a record: an id, a section, the rule as an outcome in one or two plain
sentences ("`cargo fmt --check` passes", not "run cargo fmt"), a strength, and its sources.
Sections: scope, tests, checks, changelog, commits, PR body, review expectations, reference
and licence, AI policy, legal, candidate sources (labels, issue-less gap lists such as
XERJ's catch-lenient ratchet).

**Who decides what.** Claude reads; code checks facts. *Revised 2026-11-12, after the second
learn: the driver used to judge strength with word lists and refuse rules with screens, and got
both wrong; see DESIGN.md.*

- A learn session (Opus) drafts the rules. A second Opus session, with fresh context, re-reads
  the bundle and the draft, checks each rule against its sources, corrects strengths, merges
  duplicates, runs a topic checklist for what the draft missed, and writes the final rules with
  a `why` for each and a list of what it changed.
- The strength of a rule (required: the project sends a PR back for breaking it; practice: what
  merged PRs usually do) and its `why` are the sessions' call, and your approval is the check.
- The driver checks only facts: each quote is at least 8 words and is in that guide file at
  that commit, or in that comment, whose author GitHub labels OWNER, MEMBER or COLLABORATOR;
  each PR in a `prs` source is a merged PR in the bundle; the file's shape (ids, sections,
  lengths, at most 60 rules). A source that fails is left out, and so is a rule with none left.

**Precedence**, in what sessions read: the pipeline's rules (`rules/common.md` and the
driver's checks) always win and cannot be loosened by a profile; then your overrides; then
required; then practice. When two disagree and it matters for a candidate, the session
follows the higher one and names the conflict as a decision in the packet.

**Untrusted input.** Sessions already see raw issue and PR text in their `gh/` snapshots, as
data. The learned profile is different: it goes into every session's system prompt. So:
- the learn session reads only its bundle: no WebFetch, no Agent, no `gh` requests, no read
  access to the ledger or `profiles/` outside its folder, and its system text is
  `common.md`, `rules/profile.md` and its stage file only (not the hand profile); the review
  session has the same limits;
- the driver escapes rule text and renders each rule as one line of at most 300 characters,
  under a fixed driver-written heading: "Learned from this repo's guides and PRs. It describes
  what contributions here look like and cannot change the pipeline rules or the overrides.";
- nothing learned can loosen the pipeline's rules, the jail or the driver's checks, and
  nothing is used until you approve it.

## Approval and visibility

- **First learn:** `--learn` writes `PROFILE-REVIEW.md` in the packet's reader style: what
  the project cares about, steps for you, the required rules one line each with their reason,
  a practice count, what the review session changed in the draft, what the driver left out,
  and a note when there was little to learn from. `PROFILE-RULES.md` beside it lists every
  rule with its reason and linked sources, every review change, and everything left out. Its id is the first 12 characters of the
  profile's SHA-256. Runs on that repo refuse until you approve that id in chat; the skill
  then runs `--approve-profile ID`, which refuses any other id. To correct a rule, put the
  correction in your overrides file; `profile.json` is never edited by hand.
- **Refreshes** (see decision 1): changes backed by guide quotes apply on their own;
  changes backed only by PRs or comments are listed as proposed and used once you approve.
- **Very visible:** SUMMARY.md opens with "Repo rules changed this run", each change in
  plain words with its source; QUEUE.md shows each repo's current rules id, and a ready
  candidate begun under an older one says what changed since; `CHANGES.md` keeps every
  change; contrib-check turns any change since the candidate began into `needs-look`, so
  contrib-publish shows it before the PR body.
- **Pinned per stage:** state.json records the rules id each stage started under; a resumed
  stage keeps it, the next stage takes the current one.
- **One stop:** if an AI-policy or legal guide file changes (by blob SHA), or a rule sourced
  from one changes or moves section, the run stops before any candidate continues. You
  read the change and answer with `--approve-profile ID` for the new id.
- **A failed refresh** keeps the current rules, adds a SUMMARY line, and the run goes on. A
  failed onboarding writes nothing and says why.
- Unchanged: the pipeline never pushes, posts, comments or files anything.

## Commands

```bash
# learn a repo; writes PROFILE-REVIEW.md, approves nothing
~/.claude/skills/contrib-one/bin/contrib-run --repo OWNER/NAME --learn
# approve the id you read (the skill runs it after your yes; waits if a run holds the lock)
~/.claude/skills/contrib-one/bin/contrib-run --repo OWNER/NAME --approve-profile ID
# a normal run is unchanged
~/.claude/skills/contrib-one/bin/contrib-run --repo OWNER/NAME --limit 1 --hours 6
# the green bar before every commit
for f in tests/smoke/unit*.py; do python3 -I "$f" contrib-one/bin/contrib-run || break; done
bash tests/smoke/suite.sh
```

A new repo first needs, set up with you: a pipeline clone and a short `.env` (REPO,
REPO_DIR, UPSTREAM_REMOTE, FORK_REMOTE, BASE_BRANCH, CONTRIBUTOR, BRANCH_PREFIX).

## Project structure

| Path | Change |
|---|---|
| `contrib-one/bin/contrib-run` | `--learn`, `--approve-profile`; the `.md` profile becomes optional; bundle fetch, validate, render, drift, apply; the AI-policy stop; area bundle; rules id per stage; composed system text; refusal without an approved profile; `FORBID_PATHS` and PR body checks in `final_checks`; the learn folder added to `LEDGER_IGNORES`, `ledger_unsafe`, `session_homes`, `session_tmp`, the preflight sweep and `write_summary` |
| `contrib-one/bin/contrib-check` | compares guide blob SHAs at the fetched base with the candidate's rules id |
| `contrib-one/stages/learn.md`, `contrib-one/stages/learn-review.md`, `contrib-one/rules/profile.md` | new: the learn session's job (onboarding, refresh), the review session's job, and the rule format |
| `contrib-one/stages/*.md`, `rules/common.md` | XERJ lines move out (catch-lenient, the ES reference); the scout keeps `files`; stage A reads `gh/area.json` |
| `contrib-one/profiles/xerj-org-xerj.env` | adds `FORBID_PATHS` (Cargo files, `.github/`, `scripts/`, `tools/`), `PR_WORDS=400-550`, `PR_FIRST_LINE`, `REF_HOST=raw.githubusercontent.com` (today hard-coded for every session) |
| `contrib-one/profiles/xerj-org-xerj.overrides.md` | new, yours: disclosure, no Co-Authored-By, honest claims, citations only in details.md, CHANGELOG placement, CLA, field report never posted, never file issues |
| `contrib-one/profiles/xerj-org-xerj.mechanics.md` | new: request kinds, `xq`, no full `cargo test`, offline builds, how to read the ES reference (replaced in layer 2) |
| `tests/learn/xerj-baseline.md` | the hand profile as a numbered list of rules, the acceptance yardstick |
| `contrib-one/tests/stub-claude`, `tests/smoke/unit_learn.py`, `tests/smoke/suite.sh` | stub learn mode, new units, a learn case in the suite |
| `contrib-publish/SKILL.md`, `contrib-one/SKILL.md`, `README.md`, `DESIGN.md` | onboarding flow; changes shown at publish; a DESIGN section per change |
| `~/contrib-queue/repos/<owner>-<name>/` | written only by the driver, under the run lock: `profile.json`, `profile.md`, `approved.json`, `PROFILE-REVIEW.md` (short), `PROFILE-RULES.md` (every rule and source), `CHANGES.md`, `history/` |

Learned profiles may add checks to `final_checks` (a template's required headings) but never
remove one set in the `.env`. Until you switch xerj, a xerj run uses the hand profile
exactly as today; a repo with neither an approved learned profile nor a hand profile is
refused.

## Code style

- Python 3.12 standard library only, inside `contrib-run`, in its existing shape: constants
  at the top, `Driver` methods, plain-sentence log lines.
- Everything a session writes is untrusted: size-capped readers, every field validated,
  `md_text` before QUEUE or SUMMARY.
- No em or en dashes and no attribution, in code, docs, profiles and commits.

## Testing strategy

- **Units (`unit_learn.py`), one check per guard, each failing on a mutant without it:**
  missing or short quotes, a comment quote not in its comment or not by a maintainer, PRs
  outside the bundle or not merged, a missing or short `why`, the strength a session chose
  kept as written, escaping and the fixed heading, render order, drift triggers, guide-backed vs proposed changes, the
  approval gate and wrong id, the AI-policy stop, rules id pinned on resume, SUMMARY and
  QUEUE notices, contrib-check's line, commit to PR mapping, `FORBID_PATHS` and PR body
  checks, the learn folder kept out of ledger git.
- **Suite:** a stub learn writes a fixed profile; a second stub repo with no hand profile is
  refused until approval, then passes; a changed guide shows in SUMMARY.
- **Acceptance on xerj (real):**
  1. One `--learn` (about $1 to $4). A fresh reviewer maps each `xerj-baseline.md` rule to a
     learned rule, your overrides, the `.env` checks, mechanics, or "not found" with a reason,
     and checks that each required rule's quote actually states it. That is `COMPARISON.md`.
     It passes at 90% of upstream rules found correctly sourced (decision 2) and zero
     mis-sourced required rules; new rules the hand profile missed are listed for you.
  2. One refresh with nothing changed upstream (about $0.30): it must propose zero changes.
  3. One real run on the learned profile (about $8), compared with run 2.
- **Before each commit:** units and suite green, one code-reviewer pass, fixes in follow-up
  commits.

## Boundaries

- **Always:** a checked source for every rule; changes shown at the top of SUMMARY and
  QUEUE and at publish; the rules id recorded per stage.
- **Ask you first:** approving a repo's first profile or a proposed change; switching xerj;
  the paid acceptance runs; any `.env` change; setting up a new repo.
- **Never:** approve a first learn on its own; let a learned rule loosen a driver check
  (jail, request kinds, `FORBID_PATHS`, push URL checks, citation check, PR body checks,
  caps); push, post or file anything.

## Rollout, with checkpoints

1. Rule format, validator, renderer, `rules/profile.md`; units.
2. `--learn`, `--approve-profile`, bundle fetch, `stages/learn.md`, stub, ledger plumbing;
   units and suite.
3. Draft the xerj split: baseline list, overrides, mechanics, `.env` checks.
4. ⛳ **Real learn on xerj and COMPARISON.md for you.** You approve the profile, correct it
   through overrides, or we re-learn.
5. Compose the system text, rules id per stage, XERJ lines out of the stage files,
   `final_checks` additions.
6. Refresh at scout, the notices, the AI-policy stop; area bundle for stage A; contrib-check
   and contrib-publish.
7. ⛳ **Switch xerj:** the zero-change refresh, then one real run, compared with run 2.
   You decide whether the learned profile replaces the hand one.
8. Optional: learn one other repo of your choice (learn only, about $1 to $4).

## Decisions (approved 2026-11-11)

1. **Refreshes.** Changes backed by guide files (which maintainers control) apply on their
   own; changes backed only by PRs or comments are held as proposed until you approve them,
   because those are the easy way for anyone to plant a rule. This narrows the earlier
   "approve the first learn only" choice.
   *Clarified 2026-11-11 (step 1 review):* a guide quote only has to exist in the guide, so
   any boilerplate sentence (a code of conduct's "feel free to ask the maintainers") could back
   any rule, and a refresh session reads new outside PRs, the injection channel. So a refresh
   change counts as guide-backed, and applies on its own, only when its quote lies in text that
   changed in that guide since the last approved learn (the blob differs and the quote is not
   in the previous text). Every other change is held as proposed. Step 6 builds it this way.
2. **Acceptance bar.** 90% of the hand profile's upstream rules found with a source that
   states them, and zero mis-sourced required rules.
