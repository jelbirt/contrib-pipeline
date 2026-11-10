# Contribution pipeline: design (built 2026-11-07; see "As built" at the end)

Goal: run the loop this session ran by hand (scout, claim check, repro, root cause,
weigh approaches, failing tests, fix, checks, review, PR body, trim) unattended for
2 to 4 candidates per working session or night, leaving review packets for the user.
Nothing is pushed or posted without the user's explicit "push and open".

## Constraints that shaped it
- Machine: WSL VM, 12 GB RAM of a 16 GB host, 3 GB swap, vhdx on C:. Every cargo command
  runs through `~/contrib-pipeline/tools/guarded.sh` (-j 4, start floor 32 GB on C:, kill floor
  20 GB, MemAvailable floor 2 GB, swap growth and near-full caps, waits for memory, one retry).
  Builds are strictly one at a time. No full crate test suites locally; CI runs them.
- Usage: subscription limits, not dollars. `--max-budget-usd` only applies to API billing.
- Upstream: maintainers' attention is the scarce resource (xerj AGENTS.md: patched defect
  goes in a PR with a fail-before test; speculation gets nothing; disclosure line; no
  Co-Authored-By; CLA via .contributors).
- User rules (global CLAUDE.md and memory): no em dashes anywhere; no attribution lines;
  one code-review subagent pass per diff before the PR; findings land as follow-up commits;
  PR bodies decisions-first, trimmed of redundancy and filler; show the body and push only on
  an explicit go; check open-PR overlap (search plus trial merge) before opening; verify PR
  access first; drafts and evidence outside /tmp.
- Memories are stored per project path, so worktree sessions and other repos do not load
  them. Everything the stages need is restated in the skills and the repo profile.

## Components
1. **Driver script** (bash, on WSL; started by hand or cron). It, not the model, runs every
   build and test (a model Bash call times out at 10 min, and the guard can wait 30). Preflight each round: disk
   and memory via the guard's numbers, `gh auth status`, fetch upstream. Runs one fresh
   `claude -p` session per stage with a pinned model and permission mode. When and how it
   stops is defined in "Stopping and shutdown" below. Writes a run log to the ledger.
2. **Scout** (upgrade `repo-issue-scout`, Sonnet). Adds a ledger mode that writes
   `candidates.json`; issue-less sources (ratchet lines such as `catch-lenient.txt`,
   skipped YAML cases); an overlap check by topic and touched files against every open PR,
   not only PRs that reference an issue (the #2960 vs #2964 miss); skips `rejects.md` and
   anything already packeted.
3. **`contrib-one` skill** (one candidate per fresh session, Opus). Stages: claim and
   overlap recheck; create the one live worktree; repro on a scratch node (own port and data
   dir); root cause with file:line; two or three approaches judged by an independent
   approach-critic agent; failing tests proven to fail; fix; checks through the guard;
   code-reviewer pass with fixes as follow-up commits; commit messages in repo style; PR
   body; trim pass; packet; remove the worktree, keep the branch. Scope rule: the smallest
   version that matches the reference behaviour; extras become follow-up candidates.
   "Needs you" stop for design or maintainer calls; abandon when the repro fails.
4. **Review packet** (the report the user reads; spec below).
5. **`QUEUE.md` digest**, rebuilt after each candidate: ready, needs you, abandoned.
6. **`contrib-publish` skill** (interactive, with the user). Change detection first (script,
   no model use, seconds): fetch, diff upstream since the packet's base against the branch's
   files and crates, trial merge, and the full overlap procedure (topic search plus
   `git merge-tree` against every open PR, not only new ones). Outcomes:
   - Branch still merges cleanly and nothing it touches changed upstream: no rebase. The head
     is the SHA already validated, so no re-test (CONTRIBUTION_REVIEW only requires tests on
     the final head, and this is it). Expect this to be the exception: all four PRs this week
     needed a CHANGELOG rebase.
   - Any rebase (CHANGELOG or ratchet conflicts included): the head changes, so rerun that
     PR's own tests and the ES-YAML gate on the final SHA, then refresh the body's Checks
     line. Full crate suites stay with CI, as now.
   - Same-crate code changed upstream: the above plus clippy and any tests near the changed
     code.
   - New overlap or claim: stop and flag; no rebase.
   Then walk the user through the packet with visuals, show the body, push and open only on
   an explicit go.
7. **Repo profile** (`profiles/<repo>.md`): check commands, guard use, scratch-node recipe,
   ES-YAML gate, CHANGELOG placement, PR template and disclosure, CLA, contribution gates.
8. **Ledger repo** `~/contrib-queue` (git, local only, no remote):
   `candidates/<slug>/{packet.md, PR_BODY.md, commits.md, evidence/}`, `QUEUE.md`,
   `rejects.md`, `runs/`.
9. **Disk**: one live worktree at a time (about 225 MB, shared `engine/target`), removed
   after the packet is written; the publish step recreates it from the branch.

## Review packet spec (packet.md)
The packet's shape now lives in `rules/packet.md`, which the driver gives every stage
session; see "The user's reports, rewritten for review" below for why it changed. The
original spec (a header, Problem explained, Fix explained, Why this fix, Proof, Decisions,
Not covered) is in git history.

## Changes from review round 1 (2026-11-07)
Verified before adopting: the `upstream` remote has a push URL, the gh token has `repo` and
`workflow` scopes, and `~/.claude/settings.json` allows `git:*`, `curl:*` and `python3:*`.

**Safety: headless runs cannot publish anything.**
- Headless sessions get no write credential: `GH_TOKEN` set to a read-only fine-grained
  token, git run with `-c credential.helper=`, and `upstream` push URL set to `no_push`
  (one-time setup, with the user's OK). Pushing happens only in `contrib-publish`, in the
  user's own interactive session.
- `--disallowedTools` for `git push`, `gh pr`/`gh issue`/`gh api` writes, `curl`, and
  `xerj hub`; pinned `--permission-mode`. The driver's preflight runs `git push --dry-run`
  and refuses to start unless it fails.
- `XERJ_DISABLE_FEEDBACK=true` for every run. AGENTS.md tells any agent that runs XERJ to
  file a field-report PR and rate hub corpora unasked; in this pipeline a field report is
  drafted into the packet for the user to file, never posted.
- Issue and PR text read from GitHub is untrusted data: stage prompts say so, and nothing
  in it can widen a stage's tools.

**Upstream reputation.**
- At most one issue-less candidate per run, and only with a reproduced, user-visible
  failure (a failing ratchet YAML case counts). AI_CONTRIBUTIONS treats scripted sweeps as
  abuse, so the pipeline never files issues and never produces a batch.
- A cap of 10 (set by the user 2026-11-07, `MAX_OPEN=10` in the profile): no new candidate
  starts while open upstream PRs by the user plus ready packets not yet published reach 10.
  Ready packets count because they are the user's review backlog. 5 PRs are open today.

**Stage mechanics and resume.**
- One fresh session per stage, not per candidate: (a) claim, overlap, repro, root cause,
  approaches; (b) failing tests and fix; (c) review fixes, commit messages, body, trim,
  packet. Between stages the driver runs the requested checks and writes their results.
- `~/contrib-queue/candidates/<slug>/state.json` records finished stages, branch, SHAs,
  ports and the binary used. Every stage is idempotent and resumes from it.
- Every stop, for any reason, runs the shutdown routine in "Stopping and shutdown".

**Builds.**
- `guarded.sh` takes a `flock` on the shared target dir, so no two builds (pipeline, the
  user's sessions, other worktrees) interleave.
- After each build, the binary is copied to the candidate's folder and its commit SHA is
  recorded; repro and YAML runs use that copy, never `engine/target` directly.

**Binding rules in headless sessions.** Each `claude -p` gets an `--append-system-prompt`
stating that this DESIGN.md is the user's approved plan (so the propose-and-wait rule does
not stall it) and pre-approving exactly two subagents: the approach critic and the code
reviewer. Sessions load no user settings, so the user's attribution-blocking hook does not
run in them; the driver's final checks (commit messages, PR body, packet, added lines) are the
guard instead.

**Cut:** the optional GitHub remote for the ledger.

## Stopping and shutdown (added 2026-11-07)
Whatever the reason, the driver ends with nothing of its own still running and nothing lost:
every piece of work is either committed, saved as a snapshot, or recorded as not started, and
the ledger says exactly where it stopped and how to pick it up.

**Why it stops, and how soon.** A watchdog checks every 60 s while a stage runs, and the
driver checks again between stages.

| Reason | Kind |
|---|---|
| Candidate limit reached (default 3, set per run), no good candidates left, open-PR cap reached | soft |
| Deadline less than one stage away (default: stage budget 90 min) | soft |
| `touch ~/contrib-queue/STOP` | soft |
| C: free under 26 GB (between the guard's 32 GB start and 20 GB kill floors) | soft |
| Two candidates failed in a row | soft |
| Usage-limit or auth error from `claude -p` | hard |
| Guard killed a build for memory twice (after its own retry) | hard |
| C: free under 22 GB, or MemAvailable under 2 GB for 5 min | hard |
| Ctrl-C, terminal closed, SIGTERM | hard |
| `touch ~/contrib-queue/STOP-NOW` | hard |

Soft: finish the current stage, then shut down. Hard: interrupt now, then shut down. Running
at the soft thresholds first means the guard's own kill is the last resort, not the plan.

**Shutdown routine (same steps for every reason, each step logged):**
1. Stop starting things: no new stage, build or candidate.
2. Stop the running `claude -p` session (SIGINT, 60 s grace, then SIGTERM). Its session id is
   in state.json, so `claude --resume <id>` can show what it was doing.
3. Stop the running build or test: SIGTERM to the guard, whose trap kills the whole process
   group; 30 s grace, then SIGKILL to that group only. The shared target dir is left as is
   (cargo recovers on the next build). The `flock` is released when the guard exits.
4. Stop scratch nodes this run started, by the pid and port recorded in state.json: SIGTERM,
   wait for the port to close, then SIGKILL. Delete their scratch data dirs (test data, always
   rebuilt). Never touch a process the run did not start: the user's node on 9200, other
   sessions, other worktrees.
5. Make the worktree safe:
   - A rebase, merge or cherry-pick in progress is aborted (`--abort` returns the branch to
     its last commit, nothing committed is lost).
   - Uncommitted changes are saved: a patch file into the candidate's ledger folder, and a
     snapshot commit on a separate local branch `contrib-wip/<slug>` (never the PR branch,
     so it can never be pushed by mistake). The routine checks the snapshot holds the same
     diff before going on.
   - Only then is the worktree removed (`git worktree remove`, which refuses if anything
     is left unsaved; on refusal the worktree is kept and listed in QUEUE.md). Branches are
     never deleted; nothing is ever `reset --hard`.
6. Write state.json for the candidate: stage reached, stop reason and kind, last good SHA,
   snapshot branch and patch, binary used, what the next stage would do.
7. Rewrite the top of QUEUE.md with a "Stopped" banner: when, why, what was running, what
   was saved where, and the one command that resumes. Commit the ledger.
8. Verify nothing is left: no live pid from the run's process groups, recorded ports closed,
   lock free. Anything still alive is named in the banner rather than silently left.
9. Exit with a code that names the reason (0 done, 10 soft stop, 20 hard stop, 30 shutdown
   step failed and the banner says which).

**Not reachable:** a Windows sleep, `wsl --shutdown` or power loss gives the driver no chance
to run the routine. The next run's preflight finds the stale state (dead pids, a leftover
worktree, a stale lock), runs steps 4 to 8 for it first, and adds it to the banner.

**Picking it up:** `contrib-run --resume` reads state.json and restarts the stopped candidate
at its stage, restoring the worktree from the PR branch plus the snapshot. `contrib-publish`
treats a stopped candidate as "needs you" and shows its packet with what is missing.

## As built (2026-11-07, after review round 2)

Review round 2 found that session-written code still ran unjailed in builds, tests and the
scratch node, and that sessions could reach driver-owned files. The user chose a jail per
build. What changed from the sections above:

- **Two layers of isolation.** Sessions run in Claude Code's sandbox (bubblewrap) with
  `--setting-sources ""`, `--strict-mcp-config` and an empty MCP config, Read denies on every
  credential path and `/proc`, and Edit allowed only in the candidate's clone and its
  `session/` folder. Everything the driver runs on session code (cargo fetch, fmt, clippy,
  build, test, the node, the YAML runner) runs in a second bubblewrap jail: home hidden
  except the toolchain, its own `CARGO_HOME` and target dir, no network except for
  `cargo fetch`, and a fresh pid namespace. The node is reached through a socat bridge.
- **Repositories.** The pipeline works in its own clone, `~/contrib-work/repos/xerj`, whose
  remotes cannot push. Each candidate gets a throwaway clone at `~/contrib-work/clones/<slug>`;
  its branch and any unfinished work (`refs/contrib-wip/<slug>/<n>`) are fetched back
  into the pipeline clone before the clone is deleted. The user's checkout is touched
  only by contrib-publish, for the final push.
- **Ledger layout.** `candidates/<slug>/` holds the driver's `state.json`, `results/` and
  `gh/`; the session writes only `session/` (`next.json`, `plan.md`, `packet.md`,
  `PR_BODY.md`, `evidence/`). The driver reads session files without following links.
- **One run at a time.** A ledger lock (`.run.lock`) refuses a second run (exit 40), and
  the build guard holds one global lock, so builds never overlap across projects.
- **Publish.** `contrib-check` has seven verdicts (adds `needs-look` and `retest-merge`),
  checks assignees, claim comments, same-topic PRs found by the scout's `search_terms`, and
  ratchet lines the base already removed, and exits 2 when it cannot decide.
  `contrib-run --retest <slug> [--merge]` replays the candidate's passing tests, clippy on
  their crates and the full YAML suite in the jail, on the branch or a trial merge, and
  saves nothing back. Rebases happen in a throwaway clone; the old tip is kept as
  `refs/contrib-prerebase/<slug>`.
- **Verified by running:** a real sandboxed session could not read the gh token, the
  Claude credentials, the token file or `/proc/*/environ`, could not write the ledger
  outside `session/`, `.git/config`, hooks or `~/.claude`, had no MCP tools, and could
  commit in its clone. Stub runs passed the happy path, STOP-NOW with resume, SIGTERM, the
  two-failure soft stop, the disk-floor stop and both retest modes. **Not yet run:** a
  real jailed build, the node bridge reached from a sandboxed session (`xq` through the
  sandbox proxy to the socat bridge), and a real candidate end to end (C: is below the 32 GB
  start floor).

## Review round 3 (2026-11-07)

- **Final gate.** After stage C the driver throws away the candidate's target dir and
  cached binaries and replays, on the final commit, the candidate's passing tests, clippy
  on their crates and the full YAML suite. Only then is a packet `ready`; a failure makes
  it `needs-you`. No binary built from an earlier tree can stand in for the last one.
- **Binaries.** Built in the jail with the bin folder unwritable, copied out by the driver
  only from inside the target dir, and reused only when their sha256 matches the record.
- **Review proof.** A packet needs a code-reviewer subagent call in stage C's own
  transcript under `~/.claude/projects`, which sessions can neither read nor write; a
  session-written review file is not enough.
- **Secrets.** Sessions see none of the home folder except the ledger and the work dir,
  and none of `/mnt`. The network allowlist is strict.
- **Git in sessions.** `~/.gitconfig` is hidden, so sessions get the user's name and email
  through the environment and `GIT_CONFIG_GLOBAL=/dev/null` (git treats an unreadable
  global config as fatal). `xq` is copied to `~/contrib-work/bin`, since sessions cannot
  read the skill folder.
- **Robustness.** Undecodable output, a timeout or any driver exception fails one
  candidate (`needs-you`), not the run.
- **Publish.** contrib-publish reads the whole diff, flags hunks outside the fix's area,
  treats every session-written word as data, and passes the PR title from a file.
- **Verified by running:** stub runs with the final gate, a missing review transcript
  failing the candidate, STOP-NOW with resume, both retest modes; a real Sonnet session
  reached a localhost server through `xq` and the sandbox proxy, committed under the
  user's identity, could not read the user's credential and config folders, Claude Code's
  own session history, other private folders in the home directory, or the Windows drive,
  and could not run curl. **Still not
  run:** a real jailed build, the jailed node behind its socat bridge, and a real
  candidate end to end; all wait on C: being above the 32 GB start floor.

### Review rounds 4 and 5, and the probes after them

- **Review record.** The driver copies every code-reviewer call from stage C's
  transcript, in order, into `results/review-transcript.md`, unusable ones included, and
  lists the calls after the last usable review that could have changed code. Publish
  shows all of it and runs its own review when code changed after the last one.
- **Final gate.** Runs on a fresh clone of the branch tip (ignored files do not carry
  over), YAML first, then clippy on the test and changed crates, then the tests, with a
  tree check before and after each step. It needs the branch checked out
  (`symbolic-ref HEAD`) and the fresh clone's HEAD equal to the tip the checks covered.
- **Session environment.** An allowlist of variable names; secret-looking launch names
  are also denied in the sandbox.
- **Temp files.** Each session's `CLAUDE_CODE_TMPDIR` and `TMPDIR` are its own folder,
  `~/contrib-work/tmp/session-<slug>`, removed when the candidate finishes. All of
  `/tmp/claude-<uid>` is hidden. The sandbox still lets a session write new files into
  that root and list the folder names there; it cannot read any existing content.
- **Sandbox masks.** Inside the sandbox, Claude Code lays `/dev/null` over shell and git
  startup files and editor folders in the working folder (`.bashrc`, `.gitconfig`,
  `.gitmodules`, `.mcp.json`, `.idea`, `.vscode`, `.claude` and the like). Each clone's
  `.git/info/exclude` lists them, so `git status` stays clean.
- **Sessions.** An id is recorded only once the session exists; an interrupted first
  turn is resumed through its pending id; a lost session restarts once.
- **Publish.** The approved body goes to a ledger file with content checks; the push is
  pinned to the reviewed SHA in one `set -euo pipefail` block; the PR opens only when the
  fork's branch equals that SHA. After a rebase, publish needs a passing retest on the
  new tip and shows the range-diff.
- **Verified by running:** the stub suite after each round; real Sonnet probes for the
  temp folder (mktemp and Python tempfile land in the session folder), the masks (clean
  status), the node bridge through `xq`, and hidden credentials. **Still not run:** a
  real jailed build and a real candidate end to end.

### Review round 6

- **Publish always reviews.** contrib-publish runs the code-reviewer on the final diff before
  every push. A session transcript cannot tie a review to a commit (a reviewer call can run
  commands, a background command can land after it), so the session's reviews are evidence
  only. The driver's record still lists later reviewer calls, background commands and
  writes outside `session/` (paths resolved first) as changes the review may have missed.
- **Tags.** Fetches out of session clones use `--no-tags`, and publish names every ref in
  full (`refs/heads/fix/<slug>`, `refs/remotes/upstream/main`), so a session's tag cannot
  stand in for the branch.
- **Temp folders.** Named `cand-<slug>` and `scout-<run id>`, removed at finish and after
  the scout on any exit, and swept at the next start. The Read tool is also denied all of
  `/tmp/claude-<uid>`.
- **Ignored-files log** leaves out the sandbox mask names, so real leftovers show.

## After the first real run (2026-11-08)

Run 1 took one candidate (`max-buckets-cluster-setting`) through scout and stage A. Stage A
worked as designed, but the driver recorded its fail-first test as not met (the compile-error
pattern matched cargo's "error: test failed" trailer), so the session stopped with a question.
Changes since:

- **Fail-first check.** Only `error[E....]:` or `error: could not compile` counts as a compile error.
- **gh reads.** `--repo` and `--repo=` naming the profile repo are accepted. Arguments, search
  terms and `--search` values that name a URL, `github.com`, or a `repo:`, `org:`, `user:` or
  `owner:` qualifier are refused, so the driver's token cannot be pointed at another repo.
- **`--answer SLUG TEXT`.** Accepted only for a needs-you candidate of the same repo whose clone
  was saved. The answer is written just before the candidate runs, after preflight, the cap
  and the stop files, so a run that stops earlier leaves the question as it was. The stage that
  asked resumes in its own session with the answer; a question raised after stage C (the final
  gate, or a driver error there) reopens C instead of rerunning the gate on unchanged code.
  `asked_by` records whether a session, the gate or the driver raised it. A candidate stopped
  after the answer was recorded continues with `--resume`.
- **Build folders.** Kept for needs-you candidates (a cold build was 12.6 minutes), dropped
  after `KEEP_BUILD_DAYS` (default 14) or oldest first while C: is below the start floor.
- **Audit trail.** Transcripts and subagent transcripts are gzipped into the candidate folder
  (Claude Code deletes its own after 30 days); `runs/<id>/SUMMARY.md` lists sessions, turns,
  minutes, cost (this run's share of each session's cumulative figure), denials and driver
  requests. The ledger is committed again after shutdown and after the exit line.
- **Instructions.** Sessions are told to read ES source with WebFetch (curl is denied), to make
  needs-you questions stand alone, and to treat the scout's suggested fix as a hypothesis.
- **Tests.** `tests/stub-claude` is the permanent stub; stub runs covered the happy path,
  needs-you then answer, an answer held back by a STOP file, a gate-raised answer reopening C,
  the refusals, STOP-NOW mid-B with resume.

## Review rounds 8 and 9 (2026-11-08, before resuming the first real candidate)

- **Ledger git never enters a session folder.** The ledger ignores `candidates/*/session/`
  and `runs/*/scout/session/`; the driver copies an allowlist of plain files (packet, PR
  body, plan, next.json, candidates.json, evidence text) into a driver-owned `record/` and
  commits that. Every commit first rewrites the ignore rules, untracks session files with
  `git rm -f --cached` (no status run inside a nested repo), and refuses to commit while a
  gitlink or a session file is tracked or any other nested `.git` exists. contrib-publish
  commits through `contrib-run --commit-ledger`. Proven by running a planted nested-repo
  filter: it ran under the old driver and under round 8 on an upgraded ledger, and does not
  run now.
- **`without` runs** touch the real files afterwards (paths rechecked inside the clone), so
  cargo cannot reuse a build of the base code. Proven on a small crate: a false pass before
  the touch, a real failure after.
- **Session errors** (an overloaded API, a timeout) are retried once after 60 s in the same
  session and do not use up a turn; a second error in a row stops the run softly, leaving
  the candidate resumable.
- **Final gate** adds `cargo fmt --all --check` and runs clippy as CI does
  (`--workspace --all-targets`, without incremental data or debuginfo, its output removed
  afterwards; sessions cannot ask for the workspace form). A memory kill, full disk or lock
  timeout in the gate stops the run softly instead of failing the candidate. The YAML run
  waits for `/_cluster/health` and reports a node that never comes up as an infrastructure
  failure.

## Review round 10 (whole pipeline, 2026-11-08)

- gh `--jq` is gone (gojq could read the driver's environment) and host gh runs with an
  allowlisted environment.
- Before any host git reads a candidate clone, the driver refuses a `commondir`, `gitdir`,
  alternates file or symlinked objects or refs: git follows them to other repositories.
- Host git never reads `~/.gitconfig`; the identity comes from the environment.
- Disk floors are soft 32 GB and hard 26 GB, matching the guard; a guard that cannot start a
  build (exit 99) is a soft stop, and the lock wait is one hour.
- A replayed test that now matches no test is reported in the gate, not counted as a failure,
  when another replayed test passed.
- An unreadable next.json gets one retry turn. Used-up turns, two bad next.json files and final
  checks that still fail after the fix-up turn all become `needs-you` (asked by the driver), so
  `--answer` can carry the same session on.
- An inherited SIGHUP ignore (nohup) is kept; the launch line uses `setsid nohup`.
- `--answer` is not blocked by the open-PR cap; retest checks formatting; gh snapshots and
  transcripts stay on disk but out of the ledger's git.
- contrib-check measures the branch from where it meets the base now and fetches PR heads to
  private refs. The guard's `-j` check reads whole tokens only.

## Review rounds 11 and 12 (2026-11-08)

- **Saving a clone never reads the session's .git.** The driver hard-links a copy of `.git`
  into `~/contrib-work/snap/<slug>`, a folder no session can write, and checks the copy:
  plain folders and regular files only (no symlinks, FIFOs, sockets or devices), every folder
  listable, no `commondir`, `gitdir` or alternates, and no `include` keys in its config. It
  then replaces the copy's config with a minimal one and fetches from the copy with
  `git-upload-pack --strict`, `transfer.fsckObjects` and a time limit. A session process that
  outlives its turn can no longer swap `.git` between the check and the fetch, steer the host
  with its config, or hang the driver on a FIFO. Host git calls now have a time limit.
- **The guard says when it, not the command, stopped a run.** `guarded.sh` writes its own
  exits to `$GUARD_STATUS` (a driver-owned file); exit codes 97 to 99 count as infra only with
  that file. Only "not started" stops the run, and then the rest of the turn's requests are
  skipped and the candidate is stopped, resumable. A STOP file or a deadline lets the current
  stage finish its requests as before, and leaves the final gate for `--resume`.
- **Tests cannot quietly disappear.** An ignored test counts as a failure. Every final gate
  replays every recorded test, so a renamed or removed one is reported again at each gate,
  and contrib-publish shows the list.
- **Smaller:** driver-raised questions count toward the failures-in-a-row stop; the soft disk
  floor is skipped in stub mode; contrib-check measures base changes from the merge base.
- **Tests:** `tests/smoke/suite.sh` runs in a fresh folder and checks its own results (it
  once printed old results and looked green); `tests/smoke/unit_fetch.py` runs each attack
  layout against the clone save.

## Review round 13 (2026-11-08, before resuming the first real candidate)

- **The copy step itself follows nothing.** `cp -a -l` looked every path up again by name,
  so a session process still alive during a save could swap a folder in `.git` for a symlink
  while `cp` ran and get host files hard-linked into the copy, and a `.git` swapped for a
  symlink left `snap/<slug>` as a symlink that `rmtree(ignore_errors=True)` silently kept for
  the next copy to follow. The driver now copies in Python (`copy_git_dir`): every folder is
  opened by handle relative to its parent with `O_NOFOLLOW` and checked against what was just
  looked at, only regular files are linked (and checked after linking), folders are made
  here with mode 0700, and size and depth are capped. `remove_snap` unlinks a symlink or file
  in place of the copy and refuses to go on if anything is left. A swap race that won 3 of 5
  tries against `cp` found nothing in 400 tries against the new copy.
- **Shutdown does not read a clone while something from the run may still write it.** If a
  session or build group survives its stop, the clone is kept unread and listed as a leftover.
- **The last gate step is judged like the others.** The gate cleans untracked files before
  its final tree check too, so only changes to tracked files count.
- **A command's own exit 124 is a failure, not a machine problem.** Only the driver's time
  limit makes 124 infra; a 124 from the command (the YAML runner, say) is recorded as exit 1.
- **Tests:** `unit_fetch.py` adds the swapped-symlink, leftover-symlink, direct no-follow and
  read-only-folder cases; `unit_r10.py` gets the same host-git stand-in as `unit.py`.

## Review round 14 (2026-11-08, before resuming the first real candidate)

- **No host check reads the live .git by path.** Round 13 made the copy safe, but
  `git_dir_check` still checked the session's `.git` in place before every jailed git call and
  build: an `lstat` then a host `git config --file`, and an `os.walk`, each of which looks the
  name up again. A swap in between let a session learn whether a host file parses as git
  config, see host file names in the refusal text, or stall the driver on a FIFO. Now
  `git_dir_check` checks a copy made by `copy_git_dir` (`git_copy`, in
  `snap/<slug>.<use>`), then asks jailed git where the git dir is; the save path fetches from
  that same checked copy.
- **A build's jail binds a checked copy of .git, not the live one.** bwrap resolves a bind's
  source when the jail starts, which can be an hour after the check (the guard's lock wait).
  A `.git` swapped by then for the relative symlink `../../..` bound the home folder,
  read-only, into the jail with the session's build code: reproduced with a test home, whose
  token file became readable. `cargo_jail` now binds `snap/<slug>.build`, a path no session
  can change; a destination swapped by then can only make bwrap refuse to start the jail
  or put the copy elsewhere inside it. The build
  copy is replaced at each build and dropped when the candidate ends, after a retest, and
  (any copy left by a stop) at the next run's start.
- **The survivor rule now fires, and only for real survivors.** A group still there after
  SIGKILL during a hard stop or a time limit sets `survived`, and shutdown then keeps the clone
  unread, as round 13 said. `stop_group` now polls the leader's `Popen` when the driver
  started it: a killed leader stays a zombie until reaped, and a group holding only a zombie
  still answered `killpg`, so every time limit waited 50 s and reported a survivor. The node
  and its bridge keep their `Popen` for the same reason (`node_stop` failed every time, and
  stopped at the node without signalling the bridge); both are now always stopped.
- **Tests:** `unit_fetch.py` swaps a folder for a symlink in the middle of the copy (not
  before it), runs a real jail against a swapped `.git` (with a control that shows the old
  bind leaking), and checks git still works on the bound copy. All three unit files work in a
  temp folder they remove at exit, and exit non-zero on a failure.

## Background gc (2026-11-08, found by the smoke suite)

- **What happened.** A suite run failed in one case: `git clone` of the pipeline clone stopped
  with "failed to copy file ... .tmp-...-pack ...: No such file or directory". The fetch just
  before it had pushed the pipeline clone past git's limit of 50 packs, so git started
  `gc --auto` in the background, and that gc was rewriting the packs while the clone copied
  them. The same can happen in a real run: preflight fetches, then a candidate is cloned.
  Every suite run adds about 7 packs to the pipeline clone, which is how it reached 51.
- **No automatic gc from the driver.** `GIT_SAFE` now carries `gc.auto=0` and
  `maintenance.auto=false`, so no driver git command (host or jail, pipeline clone, candidate
  clone or ledger) starts one. A new candidate clone gets the same two settings in its own
  config: a session's commit would otherwise start a background gc there that outlives the
  session (gc detaches into its own session) and rewrites packs while the driver copies `.git`.
  Clones also inherited all 51 packs, so the first session commit would have started one.
- **gc runs in preflight instead** (`repo_gc`), for the pipeline clone and the ledger: in the
  foreground, before the run reads either, with git's default limits (6700 loose objects, 50
  packs). A failed gc is logged and the run goes on.
- **Review of this change** found that the first `repo_gc` still let a pack rewrite overlap the
  run in two ways, both reproduced. (1) On its time limit only `git gc` was killed; its
  `repack` and `pack-objects` children kept rewriting packs while the run cloned. gc now runs
  through `run_tracked` in its own process group, so a time limit or a hard stop ends all of
  it, and a time limit stops the run. (2) `gc --auto` returns at once when another gc holds
  `gc.pid`, and other tools (`contrib-check`'s fetches, a fetch by hand) still started
  background gc in the pipeline clone. `repo_gc` now writes `gc.auto 0` and
  `maintenance.auto false` into the pipeline clone's and the ledger's own config, and stops the
  run when `gc.pid` names a live gc on this host (one older than 12 hours is stale, as in git).
- **Why that gc failed.** The pipeline clone was made from a copy of a `blob:none` partial
  clone without its partial-clone settings: 12 `.promisor` packs, 8528 history blobs missing
  (none in the base tree, so builds worked). `gc` could never finish, and a session running
  `git log -p` or `git blame` on old history would have hit read errors. Repaired by hand with
  `git fetch --refetch --tags upstream` (26 s, 0 objects missing after), deleting the failed
  gc's 170 MB temp pack and `gc.log`, removing the stale `.promisor` marker, and a foreground
  gc: 2 packs, 258 MiB, fsck clean.
- **Tests:** `unit_gc.py` shows a plain fetch starting gc in a repository over its limit and
  the driver's fetch starting neither gc nor maintenance, each `GIT_SAFE` setting on its own,
  `repo_gc` packing a repository over the limit before it returns even when the repository
  asks for a detached gc, only logging on a repository with missing objects, refusing a live
  `gc.pid` and ignoring a stale one, stopping a gc that runs out of time with its child, and a
  new clone's settings. Each check fails on a copy of the driver with its fix removed.

## The smoke suite's own pipeline clone (2026-11-09)

The stub suite gave the driver the real profile, so every suite run cloned its candidates from
the real pipeline clone (`~/contrib-work/repos/xerj`) and saved their `fix/smk*` branches and
commits back into it, which is how the suite's fetch could start the gc above in the clone real
runs use. `tests/smoke/env.sh` now makes a copy of that clone in the suite's folder and points the
suite's copy of the profile at it; the driver is unchanged.

- **The copy** is a local mirror clone (object files hard-linked, refs and config its own), made
  non-bare with a detached HEAD like the real clone, because `repo_gc` skips a bare repository
  and a mirror can turn a detached HEAD into a checked-out branch. Git never changes an object
  file in place, so nothing done to the copy changes what the real clone holds. A passing suite
  deletes the copy, since after the real clone repacks it would be the only holder of the old
  packs; a failing one keeps it to look at.
- **The checks:** the 7 smk branches land in the copy; the real clone has no smk refs and none of
  the copy's smk commits (stub commits have unique ids), and its config is unchanged; preflight's
  gc ran on the copy. These check the suite's own work rather than a snapshot of the whole real
  clone, which a real run or a fetch by hand at the same time would also change. env.sh refuses
  a suite folder whose path the profile rewrite cannot carry, and checks the rewrite.

## The request limit, told to sessions (2026-11-09, found in the first ready run)

In run 2026-11-09-070714, stage B asked for 15 requests in one turn. The driver ran the first 12
(`MAX_REQUESTS_PER_TURN`) and wrote one `too-many` line into `results/index.jsonl`. The session
never saw it: the rules did not mention a limit, and the line sat among the turn's new results.
It asked for the 3 missing runs again, but its packet said they "produced no result lines", which
reads as a failure of the requests rather than a choice of the driver.

- **The rules** (`rules/common.md`) now state the limit, that skipped requests have no result,
  and to put the most needed requests first.
- **The next prompt** starts with the cut: how many ran, the positions that did not (13 to N), and
  their ids, written the way a run id is (only letters, digits, `_`, `.` and `-`, at most 60 each,
  at most 12 listed and then a count), so a session's own words never reach a driver prompt. The
  `too-many` line in `index.jsonl` carries the same text.
- **Across a stop or a resume** the note is kept in `state.json` (`cut_note`) and put first on any
  prompt that does not already hold it, including a resumed stage's first prompt; a turn that read
  it clears it. That covers a stage whose last turn was a cut, a hard stop right after the
  requests, and a retry after a session error (which resends the prompt that has it). The scout,
  which has no `state.json`, keeps it in memory, and also names how many of its requests were not
  gh reads.
- **The old `n >= MAX_REQUESTS_PER_TURN` branch** in the request loop is gone: the list is cut
  before the loop, so it could never run.
- **Tests:** `unit.py` drives `stage_loop` with a stub session. It checks that only the first 12
  run, that the cut is named in `index.jsonl` and first in the next prompt, that a turn within the
  limit leaves it out, that a stage ending on a cut opens the resumed stage's prompt with it, that
  ids are normalized and a long list is capped, and that the rules give the driver's number. The
  old driver fails the cut checks, a driver that does not store the note fails the two
  prompt checks, and the old rules fail the last.
- **Review:** one pass. It found the lost note after a stop or a resume (important), and raw ids,
  an uncapped list, the scout's count, the dead branch and test gaps (minor); all fixed here.

## The user's reports, rewritten for review (2026-11-09, asked for after the first ready run)
The first ready packet ran to 2724 words of file:line pointers, request ids and SHAs. It read
like documentation for a maintainer, and it was hard to decide anything from it. The user
reviews candidates from every corner of a project (APIs, storage, query planning, settings)
and is not a specialist in each one, so the packet now answers three questions for that
reader: what is wrong, in plain technical words; what the options were; what they must
decide. The full record moves to `session/details.md`.
- **One spec, given to every stage:** `rules/packet.md` sets the shape (title, a bold status
  line, an at-a-glance table, then The problem, Options, The fix, Decisions for you, Not
  covered, Review, Other open PRs nearby, and a footer linking details.md), the reader, the
  word limit (1100 outside the diagrams) and who writes what. `examples/packet.md`, the
  max-buckets packet rewritten by hand and approved by the user, is appended as the model.
  `system_text` gives both to every stage session after the profile. The stage files lost
  their own packet section and point at the spec.
- **The driver checks the shape:** `final_checks` runs `packet_problems` on stage C's
  packet: the title, a status starting **Ready to publish.**, every heading and row, two
  diagrams, the word limit, no `name.ext:123` pointer, and the details.md link. Each
  problem goes back to the session as a line, as the other final checks do. `details.md`
  must exist, has no dashes or attribution, and is recorded with the packet.
- **QUEUE.md:** each entry is the packet's title (linked) and, for a ready one, its status
  line. A needs-you entry shows the question on its own line and the exact `--answer`
  command. A candidate with no packet yet falls back to its state's title and reason.
  `needs-you` now asks the session to make its question decision 1 of the packet.
- **SUMMARY.md:** opens with one plain line (outcomes, minutes, cost, why the run ended), a
  table of candidates linking each packet, and a split of the time between the sessions and
  the driver's builds and tests. The old tables follow under Details. The QUEUE banner links
  it.
- **Skills:** contrib-one's "Explain what it left" and contrib-publish's step 2 now point the
  user at the packet instead of retelling it, and walk its decisions one at a time.
- **Tests:** `unit_report.py` checks the example against the rules, each kind of packet
  problem, the queue's lines and the summary's top block. The committed driver fails it, and
  so does a driver without the pointer check, the word limit or the needs-you lines. The
  stub writes a packet in the new shape and a details.md, so the suite runs the shape check
  on every ready candidate.

## The review gate and ES citations (2026-11-09, found while publishing the first ready candidate)

**What happened.** Stage C launched its code-reviewer with `run_in_background: true`. The tool result
was only a launch notice, and the reviewer's real report arrived later as a separate message. The
driver still counted the review as usable. Claude Code also writes an `api-request-blob` line that
repeats earlier tool calls and results with no `toolUseResult`, and review_check read every line
type, so that later copy replaced the real result (status `async_launched`) and passed the checks.
The result: `results/review-transcript.md` held a launch notice, `review.usable` said 1, and the two
commits stage C made after the review had never been reviewed. The user's publish pass caught it.

**Fix.**
- review_check reads only `user` and `assistant` lines, keeps the first result for each tool call
  and counts each call once, so the copies can neither replace a result nor double the "changes
  after the review" count.
- A reviewer call with `run_in_background`, or whose result says `isAsync` or `async_launched`, is
  not usable; the reason tells the session to run it again in the foreground.
- C-finish.md step 1 now says to run the reviewer in the foreground and wait for it.

**ES citations.** Run 2's commit message cited ES Java files with line numbers, which the profile
asked for. AGENTS.md says ES is read for wire semantics only, and the user's merged PRs describe ES's
behaviour without citing its files, so the user had them removed at publish. Upstream commits do
name Java files (87 of the last 3000, mostly Lucene, a few ES paths by the maintainer), so this is
the user's own style, not a project rule. Now:
- A-investigate.md and the profile say: ES path:line goes in details.md, for the user; commits,
  code comments and the PR body state ES's behaviour (version, request, response, at most a class
  name).
- The profile key `PUBLIC_FORBID_RE` (xerj: a `.java` file name, not a host such as
  `jdk.java.net`) is checked by final_checks against the commit messages and PR_BODY.md as they
  are. Lucene files are caught too, since a bare class file cannot be told apart; sessions name the
  class without `.java`.
- In the diff only a name the change brings in is refused: not one the same change removes (a
  reworded line) and not one already in the base tree (`git grep -F` at the base), because xerj's
  own code and test data already name Java files (index.rs alone has 46). The refusal names the
  file. At most 50 different names are looked up; past that the rest is reported, not passed.

**Review of this change** (one code-reviewer pass; all findings confirmed and fixed):
- Important: the diff check as first written refused Java names already in xerj, which would
  have stopped any change near them. Fixed as above.
- The pattern now starts with `\b`, so a long run of word characters is scanned once, not once
  per position (a 1 MB word takes about 0.2 s).
- A background agent or task started before the review, and a reviewer refused for running in
  the background, count as changes after the review: either can still be working when it ends.
- A reviewer that hands its report back as a message leaves only a short pointer in the result;
  the report is in `handbackReport.text` (63 such results on this machine had that shape), so
  review_check reads it there instead of refusing the review as too short.
- `tests/smoke/suite.sh`'s STOP case waited for "stage C" and "smks" anywhere in the stub log,
  which every case shares, so it could stop the run before stage C (it failed once that way). It
  now waits for the stub's own line for smks in stage C.

**Tests.** `tests/smoke/unit_review.py` builds stage C transcripts: run 2's shape (background launch
plus a later copy), a launch notice without the flag, a finished foreground review, a copy after a
real result, an edit repeated by a copy, a handed-back report, and background agents before the
review; then the citation check on each place, on moved and existing names, a host name, a line
that looks like a file header, the cap, a 1 MB word and a broken pattern, and that final_checks
runs it. Each guard has its own check: removing any one of them fails exactly that check. The
driver before this change fails 5 of the 7 original review checks and has no citation check.
