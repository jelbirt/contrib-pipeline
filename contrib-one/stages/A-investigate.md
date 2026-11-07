# Stage A: investigate

Decide whether this candidate is real, still free, and worth a PR, and pick the approach.
You may write tests in this stage, but not the fix.

## Checklist
1. **Recheck the claim and overlap** from `gh/` (fresh snapshot for this candidate). Read
   every open PR whose files or title touch the same area. Any overlap: `abandon`.
2. **Find the code.** Read the paths the candidate names and their callers. Read
   `git log` for those files: if a maintainer chose the current behaviour on purpose, note the
   commit and weigh that.
3. **Pin the reference behaviour.** For ES-compat work, read the Elasticsearch 8.13.4 source
   (raw.githubusercontent.com, approach only, never copy) and cite path:line.
4. **Reproduce.** Write the failing test first (the profile names the patterns), commit it
   alone on the branch, and ask the driver to run it with `"expect": "fail"`. Where a live
   check helps, ask for `node-start` and use `xq`. A candidate that does not reproduce is
   abandoned, with the evidence.
5. **Weigh approaches.** List two or three ways to fix it. For each: what changes, risk,
   cost on the hot path, how it matches the reference. Then spawn one `Agent` (the
   general-purpose type) as an independent critic: give it the problem, the code pointers
   and the approaches, not your preference, and ask which it would pick and what each
   misses. This is pre-approved. Record its answer.
6. **Decide scope.** The smallest change that matches the reference fully for the reported
   case and its direct siblings. If the right fix is larger than the profile allows, or
   changes behaviour a maintainer chose on purpose, end with `needs-you`.
7. **Write `session/packet.md` sections 1 to 3** (see Packet below) and `session/plan.md`: the approach, the
   files, the tests, and what is out of scope.

End with `stage-done` once the failing test is recorded (`met: true` with expect fail) and the
packet and plan are written.

## Packet (shared by stages A to C; the user reads this in the morning)
`packet.md`, in this order:
1. Header: title, source (issue link or ratchet line), branch, base SHA, status line.
2. **Problem, explained:** two or three plain sentences, then a Mermaid flowchart
   (```` ```mermaid ````, `flowchart TD` or `LR`, at most 8 nodes, real function and endpoint
   names) of today's path next to the reference's.
3. **Approaches considered:** the options, the critic's view, and the choice with its reason.
4. **Fix, explained:** two or three sentences plus a Mermaid flowchart of the changed path,
   with the new step marked. (Stage B.)
5. **Proof:** before and after test runs, YAML results, numbers, each pointing at its file
   in `results/` or `session/evidence/`. (Stages B and C.)
6. **Decisions made without you:** every choice the user might have made differently.
7. **Not covered:** what is left, and whether it deserves its own PR.
8. **Review:** the reviewer's findings and what was done with each. (Stage C.)
