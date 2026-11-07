# Stage B: fix

Implement the approach in `plan.md`, prove it, and keep the bar green.

## Checklist
1. Read `session/plan.md`, `session/packet.md`, and the failing-test results from stage A.
2. Implement the fix in the worktree. Match the surrounding code's style. Keep the change to
   what the plan names; anything extra goes under "Not covered".
3. Ask the driver for, in one `run`:
   - `fmt`;
   - each new test with `expect: pass`;
   - each new test again with `expect: fail` and `without` set to the production files you
     changed (this proves the test fails without the fix, on the same commit);
   - the existing tests of the files you touched (by target, never a whole crate);
   - `clippy` on the crates you touched.
4. Read every result. A `met: false` result is a real problem: fix and ask again. An
   `infra: true` result is the guard stopping for memory or disk: ask again once; if it
   repeats, end with `needs-you` and say so.
5. When the change touches the engine or API (for XERJ: anything under `engine/crates/`),
   ask for `yaml` with `full: true` and for the target YAML files by name. The bar is 0
   failed. If the fix flips a ratchet line, delete that line in the same commit.
6. Add the CHANGELOG entry (the profile says where).
7. Commit: the fix as its own commit with a full body; a runner or harness change as a
   separate commit before it. Never amend or rewrite stage A's test commit; if it needs
   changes, add a commit.
8. Write `session/packet.md` sections 4 and 5, and add to 6 and 7.

End with `stage-done` when the commits are in, every result you rely on has `met: true`,
and the packet is updated.
