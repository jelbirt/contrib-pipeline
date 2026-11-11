These are the user's own rules for xerj-org/xerj. They win over anything learned from the repo.

Where these differ from xerj's own guides, the difference is settled and is not a decision for
each packet: no issues are filed (AGENTS.md asks for one for a defect you have not fixed), no
Elasticsearch file and line citations go in the PR (CONTRIBUTING.md asks for peer `file:line`
citations), and commits carry no agent disclosure (AI_CONTRIBUTIONS.md asks for it in commit
prose; the PR body's first line carries it).

- Never file issues, and never post, comment or file anything on GitHub. The user publishes.
- Honest claims only: every number comes from a command that ran; split what was verified from
  what was assumed.
- No `Co-Authored-By` trailer and no other agent attribution in commits.
- The PR body's first line is exactly this sentence (the driver checks it):
  `Written by an AI coding agent (Claude Code), run by @jelbirt, who has reviewed this change.`
- The CLA is already signed: the user is listed in `.contributors`.
- XERJ's AGENTS.md asks agents to file a field report and rate hub corpora. In this pipeline
  that is never posted; draft anything worth reporting under "Field report draft" in
  `session/details.md`.
- Elasticsearch file and line citations go in `session/details.md` only. In commits, code
  comments and the PR body, state ES 8.13's observable behaviour (the request and the
  response, at most a class name) and never a `.java` file or line.
- Overlap: the same lines, YAML cases or ratchet entries as someone else's open PR means
  abandon, unless the overlap is only a CHANGELOG line.
- CHANGELOG placement: several of the user's PRs are often open at once. Put the entry under
  `### Fixed`, but not at the top: insert it before an existing entry that no open PR in
  `gh/prs.json` places its entry next to. Name the anchor in `session/details.md`; when a
  conflict with one of the user's open PRs is still likely, make it a decision in the packet.
- PR body, 400 to 550 words after trimming, in this order:
  1. the disclosure sentence above;
  2. `Fixes #N`, or `No issue: <one line on where it came from>`;
  3. `## What this changes and why`: a table `Request | ES 8.13 | XERJ before | XERJ now`, then
     **Decisions:** bullets, each a decision and its reason;
  4. `## Evidence`: each test file, what failed with the fix reverted, what passes now; one
     line on the review pass (counts, what was fixed); the ES-YAML result with the SHA;
  5. `## Checks`: the commands, as checked items;
  6. `## Not run`: full crate suites (CI), live ES, other platforms, and any gap;
  7. `## Provenance`: **Verified:** and **Assumed:** (what would falsify it).
  Then a trim pass: cut anything said twice, filler, process narration, and what the diff shows.
