#!/bin/bash
source "$(dirname "$0")/env.sh"
run() { python3 $R --repo xerj-org/xerj --hours 8 --tick 2 --stub --claude $STUB "$@" >/dev/null 2>&1; echo "rc=$?"; }
st() { python3 -c "import json,sys;s=json.load(open('$CONTRIB_LEDGER/candidates/$1/state.json'));print('$1',s.get('status'),s.get('stages_done'),s.get('reason') or s.get('stop_reason') or '')"; }
echo "== happy"; STUB_PREFIX=smkh run --limit 1; st smkh-0
echo "== one error in B"; STUB_PREFIX=smke STUB_ERROR=B:1 run --limit 1; st smke-0; grep -c 'error_turn' $STUB_LOG; grep 'retrying in 60' $CONTRIB_LEDGER/runs/*.log | tail -1
echo "== two errors in B"; STUB_PREFIX=smkf STUB_ERROR=B:2 run --limit 1; st smkf-0; grep 'two session errors' $CONTRIB_LEDGER/runs/*.log | tail -1
echo "== resume it"; run --resume --limit 1; st smkf-0
echo "== needs-you then answer"; STUB_PREFIX=smkn STUB_NEEDS_YOU=A run --limit 1; st smkn-0
run --answer smkn-0 "yes, go on"; st smkn-0
echo "== ledger"; git -C $CONTRIB_LEDGER status --porcelain | head -5; echo "session files tracked: $(git -C $CONTRIB_LEDGER ls-files | grep -c '/session/')"; echo "record files tracked: $(git -C $CONTRIB_LEDGER ls-files | grep -c '/record/')"
git -C $CONTRIB_LEDGER ls-files candidates/smkn-0 | head
echo "== gate requests"; grep -h '"gate-' $CONTRIB_LEDGER/candidates/smkh-0/results/index.jsonl | python3 -c "import sys,json;[print(json.loads(l)['id'],json.loads(l)['kind']) for l in sys.stdin]"
echo "== leftovers"; pgrep -af 'stub-claude|bin/contrib-run --repo' | grep -v 'pgrep\|eval ' || echo none
echo "== one bad next.json in A"; STUB_PREFIX=smkb STUB_BADNEXT=A:1 run --limit 1; st smkb-0; grep -c '"bad_next"' $STUB_LOG
echo "== two bad next.json in A"; STUB_PREFIX=smkc STUB_BADNEXT=A:2 run --limit 1; st smkc-0
python3 -c "import json;s=json.load(open('$CONTRIB_LEDGER/candidates/smkc-0/state.json'));print('asked_by',s.get('asked_by'),'|',s.get('question'))"
run --answer smkc-0 "carry on"; st smkc-0
echo "== ledger ignores"; cat $CONTRIB_LEDGER/.gitignore | tail -8; echo "gh tracked: $(git -C $CONTRIB_LEDGER ls-files | grep -c '/gh/')"; echo "transcripts tracked: $(git -C $CONTRIB_LEDGER ls-files | grep -c '/transcripts/')"
echo "== leftovers2"; pgrep -af 'stub-claude|bin/contrib-run --repo' | grep -v 'pgrep\|eval ' || echo none
