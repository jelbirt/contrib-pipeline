# Real learns on xerj-org/xerj and pydantic/pydantic, scored (2026-11-12)

**The third learn (Opus drafts, a second Opus session reviews, code checks only that quotes are
real) meets the bar on xerj: 19 of 21 learnable baseline rules found outright (90.5%), and the
other 2 partly. Every required rule on both repos is backed by its quote. The xerj review
document is too long to read comfortably (2,061 words).**

## Third learn: draft plus review

| | xerj | pydantic |
|---|---|---|
| Rules id | `035333818500` | `ebdde146000b` |
| Draft rules that checked out | 60 | 40 |
| Rules kept after the review | 59 | 37 |
| Required / practice / for you | 32 / 25 / 2 | 6 / 30 / 1 |
| Changes the review made | 23 | 15 |
| PROFILE-REVIEW.md words | 2,061 | 761 |
| Learn session | 48 turns, 5.1 min, ~$2.38 | 35 turns, 2.3 min, ~$1.35 |
| Review session | 58 turns, 6.4 min, ~$2.91 | 46 turns, 2.9 min, ~$1.48 |
| Total | ~$5.29 | ~$2.83 |

Both read 30 merged and 15 closed outside PRs; xerj read 30 guide files, pydantic 7.

**xerj against the 21 learnable baseline rules.** Found: 1 (fail-first-test), 2
(check-not-already-fixed, no-untested-patch), 4 and 21 (smallest-correct-pr), 5 (cargo-fmt),
6 (clippy-clean), 7 (crate-tests-not-check), 8 (es-yaml-zero-failed), 9
(yaml-case-for-es-behaviour), 10 (catch-lenient-ratchet, missed by both earlier learns), 11
(changelog-entry), 12 (no-incompatible-licence-code), 16 (honest-numbers,
verified-vs-assumed), 17 (no-co-authored-by), 18 (agent-disclosed-first-line), 19 (cla-signed,
a step for you), 29 and 31 (test-placement, router-test-4mib-stack), 38
(pr-template-sections). Partly: 22 (the learned rule names uncovered sibling paths in the body
and sends sibling gaps to sibling PRs; the baseline puts the exact same bug in a sibling path
in scope) and 24 (no-weakened-assertions asks for a product decision before changing intended
behaviour; the baseline asks for evidence of what ES does).

**Strength.** The review fixed what the word list got wrong: xerj's fail-first-test,
cargo-fmt and clippy-clean, and pydantic's assigned-before-pr ("will be automatically
closed"), are required, each with its reason; pydantic's body-permalinks is a practice. All 31
xerj and 6 pydantic required rules were read against their quotes, and each quote says the
project requires it or closes a PR without it. The one weak one is pydantic's quality-bar
("meets the project's quality standards"): backed, but not something a reviewer can check.

**What the review did.** It fixed a quote that crossed a line break, made 9 rules required and
2 practices with a reason each, merged or cut 7 rules, moved "a human reviewed it" to the
steps for you, added test placement, two merge gates and a template item, and left out
AGENTS.md's field-report request because it has a session send data to an outside service.

**Still wrong.** The xerj review lists 32 required rules with a reason each, which is too long
to read before approving. The review session costs more than the draft. reference-code-cited
asks for file:line citations of peer projects in the PR; the overrides keep Elasticsearch
citations in details.md, which still holds.

## Earlier learns (before the review session)

### The two earlier learns

| | xerj, first | xerj, second | pydantic, first | pydantic, second |
|---|---|---|---|---|
| Rules id | `973824db09f1` | `f610983291c4` | `615415509690` | `c7e6a9da40e2` |
| Rules kept | 73 | 59 | 37 | 37 |
| Required / practice / for you | 67 / 6 / 0 | 17 / 41 / 1 | 33 / 4 / 0 | 4 / 33 / 0 |
| PROFILE-REVIEW.md words | 4,256 | 1,142 | 1,842 | 709 |
| Session | 63 turns, 7.0 min, ~$2.83 | 29 turns, 3.1 min, ~$1.46 | 46 turns, 4.3 min, ~$1.32 | 16 turns, 1.3 min, ~$0.57 |

Both read the same 30 merged and 15 closed outside PRs; xerj also read 2 files merged PRs
often change.

### The 21 learnable xerj baseline rules, second learn

| # | Baseline rule | Learned rule | Result |
|---|---|---|---|
| 1 | Fix comes with a fail-first test | `fail-first-test` | found (practice, see below) |
| 2 | An unreproduced suspicion is not sent | `no-untested-patch` | found |
| 4 | One fix per PR | `smallest-correct-pr` | found |
| 5 | `cargo fmt` clean | `cargo-fmt` | found (practice) |
| 6 | Clippy `-D warnings` on touched crates | `clippy-clean` | found (practice) |
| 7 | Touched crates' tests pass | `crate-tests-not-check` | found |
| 8 | ES-YAML gate at 0 failed | `es-yaml-zero-failed` | found |
| 9 | New ES behaviour gets a YAML case | `yaml-case-for-es-behaviour` | found |
| 10 | catch-lenient ratchet only shrinks | none | missed |
| 11 | CHANGELOG entry under Unreleased | `changelog-entry` | found |
| 12 | ES read for wire semantics, never copied | `no-incompatible-licence-code` | found |
| 16 | Honest claims, Verified vs Assumed | `honest-numbers`, `verified-vs-assumed` | found |
| 17 | No `Co-Authored-By` | `no-co-authored-by` | found |
| 18 | First line discloses the agent | `agent-disclosed-first-line` | found |
| 19 | A human signs the CLA | `cla-signed` (for you) | found (new) |
| 21 | Smallest change that matches ES | `smallest-correct-pr` | found |
| 22 | Same bug in sibling paths is in scope | none | missed |
| 24 | A deliberate behaviour changes only with ES evidence | `no-weakened-assertions` | partial |
| 29 | API tests in process in `xerj-api/tests` | `router-test-4mib-stack` | partial |
| 31 | Engine tests in `xerj-engine/tests` | none | missed |
| 38 | PR body keeps the template's parts | `pr-template-sections` | found |

### Do the required rules' quotes support them?

- **xerj, 17 required: all supported.** Each quote states the duty in one sentence ("must stay
  at 0 failed", "Do not weaken or invert", "must come from a command you actually ran", "do not
  report security vulnerabilities through public ... pull requests"), or maintainers asked for
  it on 3 PRs (bring the branch current, green CI before merge).
- **pydantic, 4 required: 2 are wrong.** `quality-bar` became required on "the contribution
  does not meet our quality standards" (a description, matched on "does not"), and
  `body-permalinks` on "If you need to point to existing code, use" (a condition, matched on
  "need to").

### What is still wrong

- **Strength is wrong both ways.** The word list misses demands written as checklists or
  imperatives, so xerj's fail-first test, fmt and clippy rules, and pydantic's "assign the
  issue first" rule ("will be automatically closed"), are practices. It also over-matches, as
  above. A word list cannot read a sentence; the learn should say why a rule is required, and
  you see that reason and the quote beside each required rule in the review.
- **Misses are files the guides do not name** (the ratchet file) **and judgement** (sibling
  paths, where engine tests go). Those may stay as overrides.
