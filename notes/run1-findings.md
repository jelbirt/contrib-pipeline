# Run 2026-11-08-072733 findings (live notes, fix after the run)

## Driver bugs
1. Expect-fail check gives a false negative. The test failed as intended
   (`test result: FAILED. 0 passed; 3 failed`), but `met` came back False with the
   note "it did not compile or no test failed". Root cause: in contrib-run, about
   line 1091, the regex `^error(\[E\d+\])?:` also matches cargo's normal trailer
   `error: test failed, to rerun pass ...`. Fix: detect a compile failure only by
   `^error\[E\d+\]:` or `error: could not compile`.
2. gh requests are refused when the session passes `--repo <this repo>`
   ("gh flag '--repo' is not allowed"), so it could not read PR diffs #2957 and
   #2996. Fix: accept `--repo`/`-R` when its value equals the profile repo (then
   drop it, since the driver adds its own), and refuse any other value. Also tell
   sessions in profile.md that the repo flag is added for them.

## Not bugs
- The duplicated log lines were my monitor tailing both the run log and the
  console file. The driver writes each line once.

## Observations
- Cold jailed test build took 756 s (12.6 min) at -j 4.
- The scout took 43 s and cost $0.30 (11 turns).
- Stage A turn 1 took 10 min and committed its test itself (1945b4ea5).

## Outcome
- Stage A asked needs-you about finding 1 (correct diagnosis, no workaround), the run
  stopped at the limit, and shutdown was clean: no processes, clones, targets, nodes or
  tmp left; branch fix/max-buckets-cluster-setting kept at 1945b4ea5 in the pipeline clone.

## More weaknesses found in the review
3. Sessions are not told to use WebFetch for ES source, so stage A tried curl twice
   (both denied) and then handed the reading to a subagent.
4. A needs-you candidate cannot be answered and continued. The only resume path is for
   stopped candidates. Add `contrib-run --answer SLUG "text"` that resumes the same stage
   session with the answer.
5. finish() deletes the target dir for needs-you too, so continuing costs another 12.6 min
   cold build. Keep the target for needs-you, as for stopped; delete it on ready/rejected.
6. The ledger commit happens before the last log lines, leaving runs/<id>.log and
   live-console.txt dirty.
7. Transcripts (and subagent transcripts) are not copied into the ledger; there is no
   per-run summary (cost, tokens, wall time per stage, denials, request outcomes).
8. The scout's suggested fix ("apply the setting to the engine cap") was wrong; stage A
   corrected it. The scout spent 43 s; its "why" should be labelled a hypothesis.
9. Usage: stage A cost about $3.53 in API-equivalent usage over 3 turns, the scout $0.30.
   A full candidate is likely $8 to $12 equivalent, which matters for plan limits.
