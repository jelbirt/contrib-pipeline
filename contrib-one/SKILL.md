---
name: contrib-one
description: Run the unattended contribution pipeline for an open source repo - a driver script that scouts candidates, then works each one through investigate, fix, and review stages in sandboxed headless sessions, and leaves a review packet per candidate in the ~/contrib-queue ledger. It never pushes or posts. Use when the user says "run the pipeline", "contrib run", "start an overnight run", "work some candidates", "contrib-one", or asks to run, resume, stop, or check on the contribution queue. Publishing a finished packet is the separate contrib-publish skill.
---

# contrib-one

The pipeline is a script, not a conversation: `bin/contrib-run` does the loop, and each
stage runs as its own headless Claude session inside the sandbox. Your job in a live
session is to start it, watch it if asked, and explain what it left. Design and the
reasons behind every choice: `DESIGN.md` in this folder.

## Start a run

Check first, in this order, and stop to tell the user if one fails:
1. A profile exists for the repo: `profiles/<owner>-<repo>.env` and `.md`. Only
   `xerj-org-xerj` exists today. A new repo needs a profile written with the user.
2. C: has at least 32 GB free (`df -BG /mnt/c`).
3. No other run is going: `pgrep -f contrib-run`.

Then start it in the background (it outlives the turn and logs to the ledger):

```bash
setsid nohup ~/.claude/skills/contrib-one/bin/contrib-run --repo xerj-org/xerj --limit 3 --hours 8 \
  > /dev/null 2>&1 &
```

Flags: `--limit N` candidates to finish (default 3), `--hours H` deadline, `--topic "..."`
to steer the scout, `--resume` to pick up stopped candidates first, `--answer SLUG "TEXT"` to
answer a needs-you candidate's question and continue only that candidate, `--model` and
`--scout-model` (defaults `opus` and `sonnet`).

Tell the user how to stop it: `touch ~/contrib-queue/STOP` lets the current stage finish (a stage
can take an hour) then shuts down; `touch ~/contrib-queue/STOP-NOW` interrupts. Either way the shutdown routine
runs: nothing is deleted that cannot be recovered, and `--resume` continues.

## Check on it
- Live log: `~/contrib-queue/runs/<run-id>.log`.
- The queue: `~/contrib-queue/QUEUE.md` lists each candidate by its packet's title and status
  line, and links the packet. Each run also writes `runs/<run-id>/SUMMARY.md`: outcomes, time,
  cost, and a link to each packet. Each candidate: `candidates/<slug>/` holds the driver's
  `state.json`, `results/` and `gh/`, and the session's `session/packet.md` (the user's review,
  in the shape `rules/packet.md` sets), `session/details.md` (the full record behind it),
  `session/PR_BODY.md` and `session/evidence/`. The work itself is on the branch, kept in `~/contrib-work/repos/xerj`.
- Exit codes: 0 done, 10 soft stop, 20 hard stop, 30 shutdown could not clean everything
  (QUEUE.md's banner says what is left).

## Explain what it left
When the user asks what happened, read `QUEUE.md`, the run's `SUMMARY.md` and the packets,
and point the user at the packets: they are written to be read as they are. Answer
questions from the packet first and from `details.md` when the user wants the evidence.
Draw a packet's flowcharts with the visualize tool when the user asks to see them. Do not publish anything from here; that is
`contrib-publish`, with the user.

## Standing rules this skill restates
No em or en dashes anywhere. No attribution in commits or PR text. Nothing is pushed,
posted or filed by the pipeline. The build guard (`GUARD` in the profile) runs every
build, one at a time.
