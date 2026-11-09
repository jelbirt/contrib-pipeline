# The packet: the user's review of this candidate

`session/packet.md` is what the user reads to understand what you found and to decide, with
confidence, whether to open the PR. The user is a technical professional but not a specialist
in this part of the code: one candidate is about an HTTP API, the next about storage, a query
planner or a settings store. Write for that reader, not for a maintainer. It is not technical
documentation. Keep it short: at most 1100 words outside the diagrams (table pipes and other
markup do not count). The full record goes in `session/details.md`.

## Shape (these headings and rows, in this order; the driver checks that each is there)
1. `# Title`: the bug in plain words, what goes wrong and where ("Cluster setting X is saved but
   ignored by searches"). Not a commit subject.
2. Status line right under the title, its first sentence in bold: `**Ready to publish.**`,
   `**Needs your decision.**` or `**In progress (stage B).**`. Then how many decisions wait on
   the user, and that nothing is posted.
3. At-a-glance table (`| | |` header), one row each, label in bold: **Area** (the part of the
   system, with a plain gloss), **The bug** (one or two sentences), **Who notices**, **The fix**
   (one sentence), **Size** (files, lines, tests), **Proof** (the before and after numbers, each
   explained), **Risk** (low, medium or high, and why in a few words). Write "not yet" in a row
   your stage has not reached.
4. `## The problem`: a **Background.** paragraph that explains the area and defines every term
   the reader may not know, then a paragraph on what the project does today against what it
   should do, then a Mermaid flowchart of today's behaviour next to the reference's. About 150
   words.
5. `## Options`: a table of at most three options (What it does, For, Against) with the chosen
   one in bold, then one line on who agreed (the critic).
6. `## The fix`: a Mermaid flowchart of the changed path with the new step marked
   (`style <node> stroke-width:3px`), two or three sentences, and a **Not checked** line for
   anything assumed rather than run.
7. `## Decisions for you`: numbered. Every choice the user might have made differently, and
   anything only the user can do. Each one: what it means in practice, then *Done:*,
   *Alternative:* and *Recommend:* lines. "None." when there are none.
8. `## Not covered`: a table: What, Why it matters, Own PR? (Yes, small / Yes / Later / No).
9. `## Review`: the review's counts by severity, then each real problem it found and what
   happened to it. Three or four sentences.
10. `## Other open PRs nearby`: whether any open PR touches the same code or behaviour, and the
    closest one, in one or two lines.
11. A footer after `---`: the PR title, a link to [PR_BODY.md](PR_BODY.md) with its word count,
    the branch, the base and head as short SHAs, and a link to [details.md](details.md).

## Writing rules for the packet
- Plain technical words. Define a term of art the first time it appears ("buckets, the groups
  an aggregation makes").
- Name code by what it does ("the merge step"), not by its path. File:line pointers, request
  ids, source quotes and full SHAs go in `details.md`, never in the packet. The driver refuses
  a source file name with a line number (`search.rs:120`, `search.rs#L120`) outside the
  diagrams.
- Explain every number where it appears: "6 of the 8 new tests fail without the fix", not a
  request id and a status.
- Diagrams: Mermaid `flowchart LR` or `TD`, at most 8 nodes, labels a reader outside the area
  understands.
- A table beats a paragraph for any comparison or list.
- The writing rules in `common.md` hold here too.

## details.md
Everything a reviewer needs to check a claim, organised under headings, with no word limit: the
source (issue link or ratchet line), the base SHA, reference source with path:line, the
file-by-file change list, every result with its request id and log path, the critic's full view,
the overlap evidence for each nearby PR, the full review table, Verified against Assumed, and
the profile's extra notes (for example a field report draft or the CHANGELOG anchor).
Quotes keep their words, but swap any em or en dash for a comma or a hyphen.

## Who writes what
- Stage A: the title, the status line, the rows it knows, The problem, Options, the decisions
  and Not covered so far, Other open PRs nearby; `details.md` started.
- Stage B: The fix, the rows The fix, Size, Proof and Risk, more decisions and Not covered;
  `details.md` gets the change list and the results.
- Stage C: Review, the final status line, Other open PRs nearby rechecked, every row filled,
  and the whole packet within the word limit.
- Ending a stage with `needs-you`: set the status line to `**Needs your decision.**` and make
  decision 1 your question, with its options and your recommendation, so the packet alone is
  enough to answer it. After the answer, set the status line back to `**In progress (stage
  X).**` and rewrite decision 1 with *Done:* set to what the user chose.

## Example
A finished packet from an earlier candidate follows. Copy its shape, length and tone, not its
content.
