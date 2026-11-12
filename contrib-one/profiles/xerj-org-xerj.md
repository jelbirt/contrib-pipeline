# Repo profile: xerj-org/xerj

Read with `rules/common.md`. Where this file and upstream's own docs disagree, upstream wins;
say so in the packet (a decision for the user when it matters).

## What upstream requires (AGENTS.md, .github/AI_CONTRIBUTIONS.md, docs/CONTRIBUTION_REVIEW.md)
- A patched defect goes in as a PR with a test that fails before the fix and passes after.
  A suspicion that was not run is worth nothing: abandon it. Never file issues, never batch.
- `cargo fmt --all`; clippy with `-D warnings` for the touched crates (the driver's gate adds
  workspace clippy as CI runs it); the crate's tests for
  the touched code; the ES-YAML conformance gate at 0 failed for any engine change.
- New ES-compatible behaviour gets a YAML case under `engine/tests/es-compat-yaml/yaml/`
  where the runner can express it. If a vendored case was failing, its line in
  `engine/tests/es-compat-yaml/catch-lenient.txt` is deleted (the ratchet only shrinks).
- CHANGELOG entry under `## [Unreleased]` / `### Fixed` for user-visible changes.
- Elasticsearch is read for wire semantics only, never copied (AGPL/SSPL/Elastic licence).
  The reference is ES 8.13.4 source: fetch the file you need from
  `https://raw.githubusercontent.com/elastic/elasticsearch/v8.13.4/<path>` with the WebFetch tool
  and cite path:line in details.md, for the user. AGENTS.md says ES is read for wire-protocol
  semantics, never for implementation, and the user's merged PRs never cite an ES file: in
  commits, code comments and the PR body, state ES's observable behaviour (ES 8.13, the
  request and the response, at most a class name) and never a `.java` file or line. The driver
  refuses any `.java` file name there (PUBLIC_FORBID_RE), Lucene's too, since a bare class
  file cannot be told apart; name a Lucene class without the `.java`. curl and wget are
  denied in your shell; do not try them.
- Honest claims only: every number from a command that ran, Verified vs Assumed split.
- No `Co-Authored-By`. The PR's first line discloses the agent. CLA: jelbirt is already in
  `.contributors`.
- XERJ's AGENTS.md asks agents that run XERJ to file a field report and rate hub corpora.
  In this pipeline that is never posted: if you have something worth reporting, draft it
  under "Field report draft" in `session/details.md`.

## Scope rules
- Smallest change that makes XERJ answer the way ES 8.13.4 does for the case at hand. Every
  sibling path that shares the exact bug (the same handler pattern, the cluster fan-out next
  to the single-node path) is in scope; neighbouring different bugs become follow-up
  candidates listed under Not covered in the packet, not extra commits.
- Changes to the YAML runner (`engine/tests/es-compat-yaml/src/main.rs`) go in their own
  commit before the fix.
- Check the git history of the lines you change (`git log -L` or `git blame`). If a
  maintainer chose the current behaviour on purpose, either show from ES source that it is
  wrong (state ES's behaviour in the commit and PR, the path:line in details.md) or stop with
  `needs-you`.
- Overlap: before writing code and again at the end, compare against every open PR (titles,
  bodies, files touched) in `gh/prs.json`. Same lines or same YAML/ratchet entries as an
  open PR by someone else means `abandon`, unless the overlap is only a CHANGELOG line.
- No new dependencies, and no edits to `Cargo.toml`, `Cargo.lock`, `build.rs`, `.cargo/`,
  `rust-toolchain*`, `.github/`, `scripts/` or `tools/`. Builds run offline against crates
  fetched from the base commit, so a new crate cannot build anyway; if the fix needs one,
  stop with `needs-you`.

## Test patterns that work here
- In-process HTTP tests: `engine/crates/xerj-api/tests/*.rs` build the router with a tempdir
  data dir (see `destructive_requires_name.rs` or `bulk_action_line_refusal.rs` on recent
  branches) and send requests with `tower::ServiceExt::oneshot`. One file per fix, named for
  the behaviour.
- Cluster behaviour: `cluster_metadata_replicates.rs` has a 3-node in-memory ring. Wait for
  `get_index(..).is_ok()` (and settings, if used) on every member before sending requests.
- Engine-level: `engine/crates/xerj-engine/tests/*.rs`.
- Prove fail-before with a `test` request carrying `"without": [paths]` and `"expect": "fail"`.

## Stage notes for this repo
- Never run `xerj hub feedback` and never file an XERJ field report. Never touch the user's
  own node on port 9200.
- Scout: the issue-less gaps are the lines in `engine/tests/es-compat-yaml/catch-lenient.txt`
  (the ratchet of known ES-YAML gaps); write the source as `catch-lenient: <line>`. A ratchet
  line that an open PR deletes is taken.
- Stage A: the reference is the ES 8.13.4 source (see above). Where a live check helps, ask
  for `node-start` and query the node with `xq`.
- Stage B: the format and lint runs are `fmt` and `clippy` on the crates you touched; run
  existing tests by target, never a whole crate. When the change touches anything under
  `engine/crates/`, ask for `yaml` with `full: true` and for the target YAML files by name;
  the bar is 0 failed. If the fix flips a ratchet line, delete that line in the same commit.
- Stage C: the final runs are the new and touched tests, `fmt`, `clippy`, and for changes
  under `engine/crates/` `yaml` full. The last overlap check includes ratchet lines.

## Request kinds the driver accepts (put them in `next.json`)
All cargo work runs in this candidate's worktree under `engine/`, through the build guard,
with the `ci-test` profile.

| kind | fields | runs |
|---|---|---|
| `test` | `crate`, `target` (`lib` or a test file name), optional `filter`, `expect` (`pass`/`fail`/`any`), optional `without` (paths reverted to the base for this run only) | `cargo test --profile ci-test -p <crate> --lib\|--test <target> [-- <filter>]` |
| `fmt` | none | `cargo fmt --all`, then reports the files it changed |
| `clippy` | `crates` (list) | `cargo clippy --profile ci-test -p ... --tests -- -D warnings` |
| `build` | `what`: `server` or `runner` | the profile's build; the server binary is copied to `bin/` with its SHA |
| `node-start` | none | a fresh scratch node from this candidate's server binary; port in the result |
| `node-stop` | none | stops it, deletes its data dir |
| `yaml` | `files` (paths under the YAML dir) or `full: true` | the ES-YAML runner against a fresh node |
| `gh` | `args` (list) | read-only `gh`: `issue view/list`, `pr view/list/diff/checks`, `search issues/prs`, `api` GET only, no `--jq` (parse the JSON yourself). The driver adds the repo; `--repo`/`-R` naming this repo is accepted, any other is refused |

Never ask for a full `cargo test -p <crate>` without a target: it runs the machine out of
memory. CI runs full suites; list them under Not run.

Query a running scratch node from your shell with `xq METHOD /path ['json body']`
(it knows the port).

## CHANGELOG placement
Several of the user's PRs are often open at once. Put the entry under `### Fixed`, but not
at the top: insert it before an existing entry that no open PR in `gh/prs.json` places its
entry next to, so two open PRs never conflict on the same lines. Name the anchor in `session/details.md`, and when a conflict with
one of the user's open PRs is still likely, make it a decision in the packet.

## PR body (approved shape, 400 to 550 words after trimming)
1. `Written by an AI coding agent (Claude Code), run by @jelbirt, who has reviewed this change.`
2. `Fixes #N`, or `No issue: <one line on where it came from>`.
3. `## What this changes and why`: a table `Request | ES 8.13 | XERJ before | XERJ now`, then
   **Decisions:** bullets, each a decision plus its reason (when ES's behaviour settles it,
   state that behaviour; no ES file or line).
4. `## Evidence`: each test file, what failed with the fix reverted, what passes now; one line
   on the review pass (counts, what was fixed); the ES-YAML result with the SHA.
5. `## Checks`: the commands, as checked items.
6. `## Not run`: full crate suites (CI), live ES, other platforms, and any
   gap.
7. `## Provenance`: **Verified:** and **Assumed:** (what would falsify it).
Trim pass: cut anything said twice, filler, process narration, and detail the diff shows.
