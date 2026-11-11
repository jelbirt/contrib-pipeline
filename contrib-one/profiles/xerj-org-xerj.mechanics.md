## How this pipeline builds and tests xerj-org/xerj

These describe the driver's tools for this repo, not the repo's rules.

- All cargo work runs in the candidate's worktree under `engine/`, through the build guard, with
  the `ci-test` profile, offline against crates fetched at the base commit. A fix that needs a
  new crate cannot build: stop with `needs-you`.
- Never ask for a full `cargo test -p <crate>` without a target: it runs the machine out of
  memory. CI runs full suites; list them under Not run.
- The driver's final gate adds workspace clippy, as CI runs it; clippy requests during a stage
  cover the touched crates.
- In-process API tests to copy: `destructive_requires_name.rs` or `bulk_action_line_refusal.rs`
  in `engine/crates/xerj-api/tests/` (on recent branches).
- Cluster behaviour: `cluster_metadata_replicates.rs` has a 3-node in-memory ring. Wait for
  `get_index(..).is_ok()` (and settings, if used) on every member before sending requests.
- Prove fail-before with a `test` request carrying `"without": [paths]` and `"expect": "fail"`.
- Query a running scratch node from your shell with `xq METHOD /path ['json body']` (it knows
  the port).
- The Elasticsearch reference is ES 8.13.4 source: fetch the file you need from
  `https://raw.githubusercontent.com/elastic/elasticsearch/v8.13.4/<path>` with the WebFetch
  tool. curl and wget are denied in your shell; do not try them.

## Request kinds the driver accepts (put them in `next.json`)

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
