# Stage B: fix

Implement the approach in `plan.md`, prove it, and keep the bar green.

## Checklist
1. Read `session/plan.md`, `session/packet.md`, and the failing-test results from stage A.
2. Implement the fix in the worktree. Match the surrounding code's style. Keep the change to
   what the plan names; anything extra goes under "Not covered".
3. Ask the driver for, in one `run`:
   - the format and lint runs the profile names (the format run first, so later runs see
     its result);
   - each new test with `expect: pass`;
   - each new test again with `expect: fail` and `without` set to the production files you
     changed (this proves the test fails without the fix, on the same commit);
   - the existing tests of the files you touched, as narrow as the request kinds allow
     (never a whole suite).
4. Read every result. A `met: false` result is a real problem: fix and ask again. An
   `infra: true` result is the guard stopping for memory or disk: ask again once; if it
   repeats, end with `needs-you` and say so.
5. Run every wider check the profile requires for the kind of change you made, the way it
   says, and meet its bar.
6. Add a changelog entry only if the profile asks for one, where it says.
7. Commit: the fix as its own commit with a full body; a runner or harness change as a
   separate commit before it. Never amend or rewrite stage A's test commit; if it needs
   changes, add a commit.
8. Update the packet: The fix (with its flowchart), the rows The fix, Size, Proof and Risk,
   and any new decisions or Not covered rows. Add the file-by-file change list and every
   result you rely on (request id, log path, numbers) to `session/details.md`.

End with `stage-done` when the commits are in, every result you rely on has `met: true`,
and the packet is updated.
