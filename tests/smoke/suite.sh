#!/bin/bash
# Stub suite for contrib-run. Each run gets a fresh folder (never the real ledger) and checks its
# own results: the last line is "SUITE PASS" or "SUITE FAIL (n)", and the exit code says the same.
export SMOKE=${SMOKE:-$HOME/contrib-smoke/$(date +%m%d-%H%M%S)}
if [ -e "$SMOKE" ]; then echo "refusing: $SMOKE already exists"; exit 2; fi
source "$(dirname "$0")/env.sh"
echo "smoke folder: $SMOKE"
fails=0
run() { python3 $R --repo xerj-org/xerj --hours 8 --tick 2 --stub --claude $STUB "$@" >/dev/null 2>&1; rc=$?; }
field() { python3 -c "import json;s=json.load(open('$CONTRIB_LEDGER/candidates/$1/state.json'));print(s.get('$2'))"; }
want() {  # want <label> <actual> <expected>
  if [ "$2" = "$3" ]; then echo "  ok   $1 = $2"; else echo "  FAIL $1 = $2 (wanted $3)"; fails=$((fails+1)); fi; }
case_() { echo "== $1"; }

case_ "happy"; STUB_PREFIX=smkh run --limit 1; want rc $rc 0; want status "$(field smkh-0 status)" ready
case_ "one session error in B"; STUB_PREFIX=smke STUB_ERROR=B:1 run --limit 1; want rc $rc 0; want status "$(field smke-0 status)" ready
want "retry logged" "$(grep -c 'smke-0: stage B session error, retrying' $CONTRIB_LEDGER/runs/*.log | awk -F: '{s+=$NF} END{print s}')" 1
case_ "two session errors in B"; STUB_PREFIX=smkf STUB_ERROR=B:2 run --limit 1; want rc $rc 10; want status "$(field smkf-0 status)" stopped
case_ "resume it"; run --resume --limit 1; want rc $rc 0; want status "$(field smkf-0 status)" ready
case_ "needs-you, then answer"; STUB_PREFIX=smkn STUB_NEEDS_YOU=A run --limit 1; want rc $rc 0; want status "$(field smkn-0 status)" needs-you
want asked_by "$(field smkn-0 asked_by)" session
run --answer smkn-0 "yes, go on"; want "answer rc" $rc 0; want status "$(field smkn-0 status)" ready
case_ "one bad next.json in A"; STUB_PREFIX=smkb STUB_BADNEXT=A:1 run --limit 1; want rc $rc 0; want status "$(field smkb-0 status)" ready
case_ "two bad next.json in A"; STUB_PREFIX=smkc STUB_BADNEXT=A:2 run --limit 1; want rc $rc 0; want status "$(field smkc-0 status)" needs-you
want asked_by "$(field smkc-0 asked_by)" driver
run --answer smkc-0 "carry on"; want "answer rc" $rc 0; want status "$(field smkc-0 status)" ready
case_ "STOP file during stage C"
( STUB_PREFIX=smks STUB_SLEEP_STAGE=C STUB_SLEEP=8 run --limit 1; echo $rc > $SMOKE/stop-rc ) &
for i in $(seq 1 60); do grep -q 'stage C\|C cwd=' $STUB_LOG 2>/dev/null && grep -q smks $STUB_LOG && break; sleep 0.5; done
sleep 2; touch $CONTRIB_LEDGER/STOP; wait
want rc "$(cat $SMOKE/stop-rc)" 10; want status "$(field smks-0 status)" stopped
want "C done, gate left for resume" "$(field smks-0 stages_done)" "['A', 'B', 'C']"
run --resume --limit 1; want "resume rc" $rc 0; want status "$(field smks-0 status)" ready
case_ "gate order"; want gate "$(grep -h '"gate-' $CONTRIB_LEDGER/candidates/smkh-0/results/index.jsonl | python3 -c "import sys,json;print(' '.join(json.loads(l)['kind'] for l in sys.stdin))")" "fmt yaml clippy test"
case_ "ledger"
want "ledger clean" "$(git -C $CONTRIB_LEDGER status --porcelain | wc -l)" 0
for d in session gh transcripts; do want "$d files tracked" "$(git -C $CONTRIB_LEDGER ls-files | grep -c "/$d/")" 0; done
want "record copies present" "$(git -C $CONTRIB_LEDGER ls-files candidates/smkh-0/record | grep -c 'packet.md')" 1
case_ "leftovers"; want processes "$(pgrep -af 'stub-claude|bin/contrib-run --repo' | grep -vc 'pgrep\|eval ')" 0
if [ $fails -eq 0 ]; then echo "SUITE PASS"; exit 0; else echo "SUITE FAIL ($fails)"; exit 1; fi
