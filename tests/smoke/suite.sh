#!/bin/bash
# Stub suite for contrib-run. Each run gets a fresh folder and its own copy of the pipeline clone
# (never the real ledger or clone; see env.sh), and checks its own results: the last line is
# "SUITE PASS" or "SUITE FAIL (n)", and the exit code says the same.
export SMOKE=${SMOKE:-$HOME/contrib-smoke/$(date +%m%d-%H%M%S)}
if [ -e "$SMOKE" ]; then echo "refusing: $SMOKE already exists"; exit 2; fi
source "$(dirname "$0")/env.sh" || exit 2
echo "smoke folder: $SMOKE"
# The suite's own work must not reach the real pipeline clone. Stub commits have unique ids, so
# that is checked directly (smk refs and commits) rather than with a snapshot of the whole clone,
# which a real run or a fetch by hand at the same time would also change.
real_cfg=$(git -C "$REAL_REPO" config --list --local) || { echo "cannot read $REAL_REPO"; exit 2; }
smk_refs() { git -C "$1" for-each-ref --format='%(objectname) %(refname)' | grep -E ' refs/(heads/fix/smk|contrib-[a-z]+/smk)'; }
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
# Wait for the stub's own line for smks in stage C (the log is shared by every case, so the
# stage and the candidate must be on one line), then stop while stage C sleeps.
seen=no
for i in $(seq 1 60); do grep 'clones/smks-0"' $STUB_LOG 2>/dev/null | grep -q '"stage": "C"' && { seen=yes; break; }; sleep 0.5; done
sleep 1; touch $CONTRIB_LEDGER/STOP; wait
want "saw smks reach stage C before the STOP" $seen yes
want rc "$(cat $SMOKE/stop-rc)" 10; want status "$(field smks-0 status)" stopped
want "C done, gate left for resume" "$(field smks-0 stages_done)" "['A', 'B', 'C']"
run --resume --limit 1; want "resume rc" $rc 0; want status "$(field smks-0 status)" ready
case_ "gate order"; want gate "$(grep -h '"gate-' $CONTRIB_LEDGER/candidates/smkh-0/results/index.jsonl | python3 -c "import sys,json;print(' '.join(json.loads(l)['kind'] for l in sys.stdin))")" "fmt yaml clippy test"
case_ "learn a repo with no hand profile"
# A second repo: the xerj profile's settings (so the suite's copy of the clone), but no .md.
sed 's#^REPO=.*#REPO=stub-org/stub#' "$PROFILE" > "$CONTRIB_PROFILE_DIR/stub-org-stub.env"
lrun() { python3 $R --repo stub-org/stub --hours 8 --tick 2 --stub --claude $STUB "$@" >/dev/null 2>&1; rc=$?; }
RD=$CONTRIB_LEDGER/repos/stub-org-stub
STUB_PREFIX=smkl lrun --limit 1; want "refused without a profile" $rc 2
STUB_REVIEW_FAIL=1 lrun --learn; want "a learn whose review fails" $rc 1
want "a failed review writes no profile" "$([ -e "$RD/profile.json" ] && echo yes || echo no)" no
want "a failed review says why" "$(cat $CONTRIB_LEDGER/runs/*.log | grep -c 'nothing was written: RuntimeError: the review session wrote no readable rules.json')" 1
lrun --learn; want "learn rc" $rc 0
pid=$(python3 -c "import json;print(json.load(open('$RD/profile.json'))['id'])" 2>/dev/null)
want "nothing approved by a learn" "$([ -e "$RD/approved.json" ] && echo yes || echo no)" no
want "review written" "$(grep -c 'Learned, not yet approved' "$RD/PROFILE-REVIEW.md")" 1
want "a second session reviewed the draft and the driver's check" "$(grep '"stage": "learn-review"' $STUB_LOG | tail -1 | python3 -c "import sys,json;j=json.loads(sys.stdin.read());print(j['draft'], j['notes'])")" "True True"
want "the review's changes are shown" "$(grep -c '^## What the review changed' "$RD/PROFILE-REVIEW.md")" 1
want "the reviewed rules are used, not the draft" "$(python3 -c "import json,sys;p=json.load(open(sys.argv[1]));r=p['rules'];print(r[0]['strength'], len(p['changes']), all(x['why'] for x in r))" "$RD/profile.json")" "practice 1 True"
want "learn session tools" "$(grep '"stage": "learn"' $STUB_LOG | tail -1 | python3 -c "import sys,json;j=json.loads(sys.stdin.read());print(','.join(j['tools']), j['builtin'])")" "Read,Glob,Grep,Edit Read,Glob,Grep,Edit,Write"
STUB_PREFIX=smkl lrun --limit 1; want "refused before approval" $rc 2
lrun --approve-profile 000000000000; want "wrong id refused" $rc 2
lrun --approve-profile "$pid"; want "approve rc" $rc 0
want "review says approved" "$(grep -c '^\*\*Approved on ' "$RD/PROFILE-REVIEW.md")" 1
STUB_PREFIX=smkl lrun --limit 1; want "run rc" $rc 0; want status "$(field smkl-0 status)" ready
want "every session read the learned rules" "$(grep 'clones/smkl-0' $STUB_LOG | python3 -c "import sys,json;print(sorted({json.loads(l)['profile'] for l in sys.stdin}))")" "['learned']"
want "the run named the rules id" "$(grep -c "profile: learned rules $pid" $CONTRIB_LEDGER/runs/*.log | awk -F: '{s+=$NF} END{print s}')" 1
want "rules tracked in the ledger" "$(git -C $CONTRIB_LEDGER ls-files "repos/stub-org-stub" | grep -cE '/(profile|approved)\.json$|/PROFILE-(REVIEW|RULES)\.md$|/CHANGES\.md$')" 5
case_ "commands mode: assignment first, then a test and a check"
# A repo whose profile runs its own commands (TEST_CMD and CHECKS) and wants assignment before any fix.
sed 's#^REPO=.*#REPO=stub-org/cmd#' "$PROFILE" > "$CONTRIB_PROFILE_DIR/stub-org-cmd.env"
printf '%s\n' ASSIGN_FIRST=1 'SETUP_CMD=true' SETUP_KEY=README.md 'TEST_CMD=python3 -m pytest {paths}' \
  TEST_EXIT_PASS=0 TEST_EXIT_FAIL=1 TEST_EXIT_NONE=5 'TEST_FILES=*_test.py' CHECKS=FORMAT \
  'CHECK_FORMAT=true {paths}' CHECK_PATHS=. GATE_CHECKS=FORMAT >> "$CONTRIB_PROFILE_DIR/stub-org-cmd.env"
printf '# stub-org/cmd\n\nA stub profile for the commands-mode case.\n' > "$CONTRIB_PROFILE_DIR/stub-org-cmd.md"
crun() { STUB_CMD=1 STUB_ISSUE=7 python3 $R --repo stub-org/cmd --hours 8 --tick 2 --stub --claude $STUB "$@" >/dev/null 2>&1; rc=$?; }
STUB_PREFIX=smkq crun --limit 1; want rc $rc 0; want status "$(field smkq-0 status)" needs-you
want asked_by "$(field smkq-0 asked_by)" assign
want "no stage before assignment" "$(field smkq-0 stages_done)" "[]"
want "no build folder kept" "$(field smkq-0 build_kept)" False
want "assign comment drafted" "$(cat $CONTRIB_LEDGER/candidates/smkq-0/session/assign-comment.md)" "Stub: may I take this?"
crun --answer smkq-0 "assigned now"; want "answer refused while unassigned" $rc 2; want status "$(field smkq-0 status)" needs-you
STUB_ASSIGNEES=someone,jelbirt crun --answer smkq-0 "assigned now"; want "answer rc" $rc 0; want status "$(field smkq-0 status)" ready
idx=$CONTRIB_LEDGER/candidates/smkq-0/results/index.jsonl
kinds() { python3 -c "import sys,json;print(' '.join(r['kind'] for r in map(json.loads,open('$idx')) if r['id'].startswith('gate-')==$1))"; }
want "session runs" "$(kinds False)" "test test check"
want "gate runs" "$(kinds True)" "check test test"
want "gate runs only the test file no replay covers" "$(python3 -c "import json;print([r['req']['paths'] for r in map(json.loads,open('$idx')) if r['id'].endswith('-changed')])")" "[['other_test.py']]"
case_ "pause, then pick"
# RUN_MODE=pause in the profile: the run saves the scout's list and works none of it; --pick works
# named ones from that list in the order given, and --mode autonomous overrides the profile. It runs
# last: its three ready packets would put the cases above at the open-PR cap, so it lifts the cap
# for itself (the profile's last MAX_OPEN wins) and puts it back at the end.
printf 'RUN_MODE=pause\nMAX_OPEN=20\n' >> "$PROFILE"
SC=$CONTRIB_LEDGER/repos/xerj-org-xerj/scouted.json
listed() { python3 -c "import json;print(' '.join(c['slug'] for c in json.load(open('$SC'))['candidates']))"; }
STUB_PREFIX=smkp STUB_CANDS=3 run --limit 3; want rc $rc 0; want "list saved" "$(listed)" "smkp-0 smkp-1 smkp-2"
want "nothing worked" "$(ls $CONTRIB_LEDGER/candidates | grep -c '^smkp-')" 0
want "QUEUE.md shows the list" "$(grep -c '^## Scouted, waiting for your pick (3)$' $CONTRIB_LEDGER/QUEUE.md)" 1
want "the banner says how to pick" "$(grep -c '^> Pick from the scouted list below with' $CONTRIB_LEDGER/QUEUE.md)" 1
want "the list is in the ledger's git" "$(git -C $CONTRIB_LEDGER ls-files repos/xerj-org-xerj/scouted.json | wc -l)" 1
run --pick nope; want "a slug not on the list is refused" $rc 2
run --pick smkp-2 smkp-0; want "pick rc" $rc 0
want status "$(field smkp-2 status) $(field smkp-0 status)" "ready ready"
want "worked in the order picked" "$(grep -o 'clones/smkp-[0-9]' $STUB_LOG | uniq | tr '\n' ' ')" "clones/smkp-2 clones/smkp-0 "
want "the unpicked one stays" "$(listed)" smkp-1
STUB_PREFIX=smko run --mode autonomous --limit 1; want "--mode autonomous rc" $rc 0; want status "$(field smko-0 status)" ready
want "an autonomous run leaves the list" "$(listed)" smkp-1
sed -i '/^RUN_MODE=/d; /^MAX_OPEN=20$/d' "$PROFILE"
case_ "ledger"
want "ledger clean" "$(git -C $CONTRIB_LEDGER status --porcelain | wc -l)" 0
for d in session gh transcripts bundle; do want "$d files tracked" "$(git -C $CONTRIB_LEDGER ls-files | grep -c "/$d/")" 0; done
want "record copies present" "$(git -C $CONTRIB_LEDGER ls-files candidates/smkh-0/record | grep -c 'packet.md')" 1
case_ "pipeline clone"
want "branches saved in the suite's copy" "$(git -C "$SMOKE_REPO" for-each-ref 'refs/heads/fix/smk*' | wc -l)" 12
want "no smk refs in the real clone" "$(smk_refs "$REAL_REPO" | wc -l)" 0
want "no smk commits in the real clone" "$(smk_refs "$SMOKE_REPO" | while read -r o _; do git -C "$REAL_REPO" cat-file -e "$o" 2>/dev/null && echo "$o"; done | wc -l)" 0
want "real clone's config unchanged" "$([ "$(git -C "$REAL_REPO" config --list --local)" = "$real_cfg" ] && echo yes || echo no)" yes
want "preflight gc ran on the copy" "$(git -C "$SMOKE_REPO" config gc.auto)" 0
case_ "leftovers"; want processes "$(pgrep -af 'stub-claude|bin/contrib-run --repo' | grep -vc 'pgrep\|eval ')" 0
if [ $fails -eq 0 ]; then rm -rf "$SMOKE_REPO"; echo "SUITE PASS"; exit 0; else echo "SUITE FAIL ($fails)"; exit 1; fi
