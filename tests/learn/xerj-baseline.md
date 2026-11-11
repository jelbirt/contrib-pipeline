# xerj-org/xerj: the hand profile as a list of rules (the acceptance yardstick)

Each rule from `contrib-one/profiles/xerj-org-xerj.md` (as of 2026-11-11), numbered, with where it
should live once xerj switches to learned rules:

- **L**: the learn should find it in the repo's own guides or merged PRs.
- **O**: your preference, kept in `profiles/xerj-org-xerj.overrides.md`.
- **E**: a driver check from the `.env` (`FORBID_PATHS`, `PR_WORDS`, `PR_FIRST_LINE`,
  `PUBLIC_FORBID_RE`, `REF_HOST`).
- **M**: pipeline mechanics, kept in `profiles/xerj-org-xerj.mechanics.md`.

The acceptance bar (SPEC.md, decision 2): at least 90% of the **L** rules found, and no
required rule with a wrong source. COMPARISON.md maps every line here to a learned rule, the
overrides, a check, the mechanics, or "not found" with a reason.

## What upstream requires

1. **L** A patched defect goes in as a PR with a test that fails before the fix and passes after.
2. **L** A suspected defect that was not reproduced is not submitted.
3. **O** Never file issues.
4. **L** One fix per PR; never batch.
5. **L** `cargo fmt --all` is clean.
6. **L** Clippy with `-D warnings` is clean for the touched crates (CI runs it on the workspace).
7. **L** The crate's tests for the touched code pass.
8. **L** The ES-YAML conformance gate shows 0 failed for any engine change.
9. **L** New ES-compatible behaviour gets a YAML case under `engine/tests/es-compat-yaml/yaml/`
   where the runner can express it.
10. **L** When a vendored YAML case starts passing, its line in `catch-lenient.txt` is deleted;
    the ratchet only shrinks.
11. **L** User-visible changes get a CHANGELOG entry under `## [Unreleased]` / `### Fixed`.
12. **L** Elasticsearch is read for wire semantics only and never copied (licence).
13. **M** The reference is ES 8.13.4 source, fetched from `raw.githubusercontent.com` (**E** `REF_HOST`).
14. **O** ES file and line citations go in details.md only; commits, code comments and the PR
    body state ES's behaviour (**E** `PUBLIC_FORBID_RE`).
15. **M** curl and wget are denied in the session shell.
16. **L** Honest claims only: every number from a command that ran, Verified vs Assumed (also
    **O**).
17. **L** No `Co-Authored-By` trailer (also **O**).
18. **L** The PR's first line discloses the agent (also **O**, the exact sentence; **E**
    `PR_FIRST_LINE`).
19. **L** A human account signs the CLA before a PR can merge (also **O**: already signed,
    `.contributors` lists the user).
20. **O** The field report AGENTS.md asks for is never posted; a draft goes in details.md.

## Scope

21. **L** The smallest change that makes XERJ answer the way ES does for the case at hand.
22. **L** Sibling code paths with the exact same bug are in scope; different bugs are follow-ups.
23. **O** Changes to the YAML runner go in their own commit before the fix.
24. **L** Behaviour a maintainer chose on purpose is changed only with evidence of ES's behaviour.
25. **O** Overlap with someone else's open PR on the same lines or YAML entries means abandon,
    unless it is only a CHANGELOG line.
26. **E** No new dependencies (`FORBID_PATHS` covers `Cargo.toml` and `Cargo.lock`; offline
    builds, rule 28, cannot fetch a new crate).
27. **E** No edits to `Cargo.toml`, `Cargo.lock`, `build.rs`, `.cargo/`, `rust-toolchain*`,
    `.github/`, `scripts/` or `tools/` (`FORBID_PATHS`; `.cargo/` at the root and under `engine/`).
28. **M** Builds run offline against crates fetched at the base commit; a fix that needs a new
    crate stops with needs-you.

## Test patterns

29. **L** API behaviour is tested in-process in `engine/crates/xerj-api/tests/*.rs` (router plus a
    tempdir data dir, requests through `tower::ServiceExt::oneshot`), one file per fix named
    for the behaviour.
30. **M** Cluster behaviour uses the in-memory multi-node ring and waits for every member (code
    knowledge: the bundle has no source files, and no guide says it).
31. **L** Engine-level tests live in `engine/crates/xerj-engine/tests/*.rs`.
32. **M** Fail-before is proved with a `test` request carrying `without` and `expect: fail`.

## Mechanics

33. **M** The request kinds table (`test`, `fmt`, `clippy`, `build`, `node-start`, `node-stop`,
    `yaml`, `gh`).
34. **M** Never a full `cargo test -p <crate>` without a target (memory); CI runs full suites.
35. **M** `xq` queries a running scratch node.

## CHANGELOG and PR body

36. **O** The CHANGELOG entry is not put at the top of `### Fixed`, but before an entry no open
    PR is next to; the anchor is named in details.md.
37. **O** The PR body is 400 to 550 words after trimming (**E** `PR_WORDS`).
38. **L** The PR body has the template's parts: what and why, Evidence, Checks, Not run, and
    Provenance with Verified and Assumed (also **O**: the order, `Fixes #N` or `No issue:`, the
    table and the headings, in the overrides).
39. **O** A trim pass removes repetition, filler, process narration and what the diff shows.

Count: 21 **L**, 8 **O**, 2 **E**, 8 **M**. Rules 16 to 19 and 38 are **L** with an **O** part
kept in the overrides; rules 13, 14, 18 and 37 also have an **E** check. At 21 **L** rules the
90% bar allows two misses. Rule 10 is the likeliest miss: only `catch-lenient.txt`'s own header
states it, and that file is not a guide.

Not a rule: the hand profile's opening line ("where this file and upstream's own docs disagree,
upstream wins") is replaced by SPEC.md's order, where your overrides win over learned rules. The
overrides name the differences that are settled.
