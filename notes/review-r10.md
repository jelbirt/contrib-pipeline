# Whole-pipeline review (round 10), 2026-11-08

Verified by running: C1 (`gh api --jq 'env.X'` printed the variable) and C2 (a host fetch from a
clone whose .git/commondir points at another repo pulled that repo's commit).

## Critical
- C1 gh `--jq`/`-q` lets a session read the driver's environment (gojq env). req_gh and gh() pass
  os.environ. Fix: drop --jq/-q from GH_FLAGS_VALUE and the api allowlist; allowlisted env for host gh.
- C2 host git fetch from the session clone obeys session-written .git/commondir (also alternates,
  gitdir, symlinked objects/refs): any user repo can be copied into the pipeline clone. save_clone
  fetch ~L1455 runs before git_dir_check; also L1489, L1502. Fix: refuse those before every host
  git on the clone; add them to denyWrite.
## Important
- I1 contrib-check diffs from the original base_sha (L91, ratchet diff L104-106/125-130); after a
  publish rebase it reports upstream files as mine. Fix: diff {main_ref}...{branch}.
- I2 gate replays every test that ever passed; a renamed test (filter now matches 0) fails the gate
  forever. Fix: zero-match = "gone", reported, not a failure, if at least one replayed test passes.
- I3 disk floors: driver soft 26/hard 22 vs guard START 32: builds refused as infra 99 while the run
  continues. Fix: soft 32, hard 26; guard rc 99 = soft stop (also covers M7 lock wait).
- I4 "failed" is a dead end for unreadable next.json, unknown action, used-up turns, final-check
  failures. Fix: one retry turn for bad next.json; turns used up and final checks go to needs-you
  asked_by driver.
- I5 SIGHUP handler overrides nohup. Fix: keep SIG_IGN if inherited; SKILL launch with setsid nohup.
## Minor
- M1 a test can print a forged "test result: ok" line: inherent; publish diff reading is the defence (note only).
- M2 soft STOP is honoured at stage boundaries, SKILL says "current step": fix text.
- M3 contrib-check uses FETCH_HEAD in the pipeline clone (races a live run): private refs, --no-write-fetch-head.
- M4 docs: profile says workspace clippy not run; publish step 2 says clippy on changed crates; TARGET_DIR unused.
- M5 retest is always cold and skips fmt: reuse targets/<slug>, add fmt --check.
- M6 guard -j check scans the whole command string: match tokens only.
- M7 guard lock wait 7200 s exceeds REQUEST_TIMEOUT: driver passes LOCK_WAIT=3600 (and rc 99 soft stop).
- M8 ledger grows: gh/ snapshots and transcripts committed every run: keep on disk, ignore in git.
- M9 RUSTUP_TOOLCHAIN=stable ignores a repo pin (xerj has none; stable = CI 1.97.1 today): note only.
- M10 open-PR cap blocks --answer: exempt answer runs.
- M11 host git reads ~/.gitconfig: GIT_CONFIG_GLOBAL=/dev/null in git_env with identity from env.
