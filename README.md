# contrib-pipeline

An unattended pipeline that finds, reproduces and fixes small upstream defects in an open
source repository, and leaves each fix as a reviewed packet for a person to publish. Nothing
it runs on its own can push, open a pull request or post anywhere.

## Layout

| Path | What it is |
|---|---|
| `contrib-one/` | The driver skill. `bin/contrib-run` runs the loop (scout, stages A, B, C, final gate); `bin/contrib-check` checks a branch for overlap and base drift; `bin/xq` lets sessions reach their scratch node; `rules/`, `stages/` and `profiles/` are what the sessions read. |
| `contrib-publish/` | The interactive skill for the morning: explain each packet, check what changed, retest only when needed, and push on an explicit go. |
| `tools/guarded.sh` | The build guard: `-j 4`, disk and memory floors, one build at a time. |
| `tests/` | `smoke/suite.sh` runs the driver against a stub Claude; `smoke/unit.py` and `exploit/` are targeted checks. |
| `notes/` | Findings from the first real run and the whole-pipeline review. |

`contrib-one/DESIGN.md` is the full design and the record of every review round.

## Where things live at run time

- Ledger (packets, state, logs, run summaries): `~/contrib-queue`, its own local git repo.
- Work area (pipeline clone, candidate clones, build targets, cargo home): `~/contrib-work`.
- The skills are linked into Claude Code as `~/.claude/skills/contrib-one` and
  `~/.claude/skills/contrib-publish`.

## Running

```bash
setsid nohup ~/contrib-pipeline/contrib-one/bin/contrib-run --repo xerj-org/xerj --limit 1 --hours 6 > /dev/null 2>&1 &
```

Stop with `touch ~/contrib-queue/STOP` (after the current stage) or `STOP-NOW`. Answer a
question with `contrib-run --answer SLUG "text"`; continue stopped work with `--resume`.

## Tests

```bash
bash ~/contrib-pipeline/tests/smoke/suite.sh
```
