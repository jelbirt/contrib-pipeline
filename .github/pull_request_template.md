<!--
Decisions first. What you decided and why goes at the top; the mechanics go
below. A reviewer should be able to stop after the first section and still know
what changed about the pipeline.
-->

## Decisions

<!-- What did this PR decide, and why? Name the decision, not the diff. If it
     answers something a run turned up, name the run or candidate. -->

## What it changes for a run

<!-- What an unattended run, a scout, a stage session or a publish does
     differently now. Call out loudly, if present:
     - anything repo-, language- or tool-specific in shared driver code or
       stage prompts (those belong in contrib-one/profiles/)
     - a new permission prompt, sandbox opening or network access
     - a change to the ledger layout in ~/contrib-queue -->

---

## Mechanics

**Files touched**

<!-- The map, not the diff. -->

**Tests**

<!-- New or changed checks, and the mutants they catch. -->

**How verified**

- [ ] `scripts/checks.sh` green (CI runs the same)
- [ ] `scripts/checks.sh --full` green: the stub suite, which CI cannot run
- [ ] One review pass over the full branch diff, findings fixed or noted
- [ ] `README.md`, `contrib-one/SKILL.md` or `contrib-one/DESIGN.md` updated if behavior changed
