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
Order, each section short:
1. Header: status, branch, base commit, upstream issue or source, overlap check result.
2. **Problem, explained**: two or three plain sentences, then a flowchart of what happens
   today next to what the reference (e.g. ES 8.13) does, using the real request path.
3. **Fix, explained**: two or three plain sentences, then a flowchart of the changed path
   showing where the new check or code sits and what each branch now returns.
4. **Why this fix**: the approaches considered, in a small table, with the critic's verdict.
5. Proof: fail-before and pass-after test lines, check results, review findings and what
   was done with each.
6. Decisions made without the user, each one line, so they can be overturned.
7. Not covered and follow-up candidates.
Visual rules: the overnight session writes the two flowcharts as Mermaid blocks in
packet.md (text, diffable, renders on GitHub and in VS Code). Diagrams name real
functions and outcomes, no prose inside boxes, at most about eight nodes each. In the
morning, `contrib-publish` renders the same two diagrams in chat as visuals (the
visualize widget in the app) before showing the PR body, and offers more on request.

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
