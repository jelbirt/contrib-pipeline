#!/usr/bin/env bash
# Run one build/test command so it cannot take WSL down.
#   Disk:   Windows C: backs the WSL vhdx. Refuse to start below START_GB, kill below FLOOR_GB.
#   Memory: the VM has 12 GB of a 16 GB host. Kill the command when MemAvailable drops below
#           MEM_FLOOR_MB (the real OOM guard), or when swap grows more than SWAP_GROW_MB past
#           what was already in use when the command started. Swap that other projects' runs
#           left behind does not count against it.
#   Busy:   when another job holds the memory at start, wait up to WAIT_SECS for it to come
#           back instead of refusing. After a memory kill, wait the same way and rerun the
#           command up to RETRIES times (cargo builds resume incrementally). RETRIES=0 for a
#           command that must not run twice.
#   Jobs:   cargo is pinned to JOBS (default 4); a command asking for more is refused.
# Exit: the command's own code; 97 refused -j; 98 killed; 99 not started.
# When GUARD_STATUS names a file, the guard writes "refused", "killed ..." or "not-started ..."
# there for its own exits, so a caller can tell them from the command exiting 97, 98 or 99.
status() { [ -n "${GUARD_STATUS:-}" ] && printf '%s\n' "$*" > "$GUARD_STATUS"; return 0; }
START_GB=${START_GB:-32}; FLOOR_GB=${FLOOR_GB:-20}
MEM_FLOOR_MB=${MEM_FLOOR_MB:-2048}; SWAP_GROW_MB=${SWAP_GROW_MB:-${SWAP_CEIL_MB:-1536}}
WAIT_SECS=${WAIT_SECS:-1800}; RETRIES=${RETRIES:-1}; JOBS=${JOBS:-4}
export CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=/usr/bin/cc CC=/usr/bin/cc
export CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-/home/user/xerj/engine/target} CARGO_BUILD_JOBS=$JOBS RUST_TEST_THREADS=${RUST_TEST_THREADS:-4}
c_gb()   { df -BG --output=avail /mnt/c | tail -1 | tr -dc 0-9; }
mem_mb() { awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo; }
swap_mb(){ awk '/^SwapTotal:/{t=$2}/^SwapFree:/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo; }
# Swap within 256 MB of full is a kill on its own, whatever was in use at start.
SWAP_CAP_MB=$(( $(awk '/^SwapTotal:/{print int($2/1024)}' /proc/meminfo) - 256 ))
pid=""
for j in $(grep -oE '(^|[[:space:]])(-j|--jobs)[ =]?[0-9]+' <<<"$*" | grep -oE '[0-9]+$'); do
  [ "$j" -gt "$JOBS" ] && { echo "guard: refusing -j $j (limit $JOBS)"; status refused; exit 97; }
done
CMD="$*"

# One build at a time on this machine, whatever its target dir: the memory limit is shared.
# The lock is held until this script exits; a command it started keeps the descriptor, so
# a build that outlives a killed guard still holds it.
GUARD_LOCK=${GUARD_LOCK:-$HOME/.cache/guarded-build.lock}
mkdir -p "$(dirname "$GUARD_LOCK")"
exec 9>"$GUARD_LOCK"
if ! flock -n 9; then
  echo "guard: another guarded build holds the lock; waiting (up to ${LOCK_WAIT:-7200}s)"
  flock -w "${LOCK_WAIT:-7200}" 9 || { echo "guard: lock wait timed out"; status not-started lock wait timed out; exit 99; }
fi

# Wait until MemAvailable is back to twice the floor and swap is below its cap, or give up
# after WAIT_SECS.
wait_for_memory() {
  local need=$((MEM_FLOOR_MB*2)) waited=0 m s
  while m=$(mem_mb); s=$(swap_mb); [ "$m" -lt "$need" ] || [ "$s" -gt "$SWAP_CAP_MB" ]; do
    [ "$waited" -ge "$WAIT_SECS" ] && { echo "guard: only ${m}MB available, swap ${s}MB used, after ${waited}s; giving up"; return 1; }
    [ $((waited % 60)) -eq 0 ] && echo "guard: $1: ${m}MB available (need ${need}MB), swap ${s}MB used (cap ${SWAP_CAP_MB}MB); waiting (${waited}s of ${WAIT_SECS}s)"
    sleep 5; waited=$((waited+5))
  done
}

# One run of the command. Sets rc, reason ("" | disk | memory) and the low/high marks.
run_once() {
  local c m s s0 why=""
  c=$(c_gb); m=$(mem_mb); s0=$(swap_mb)
  echo "guard: start C: ${c}G, mem ${m}MB avail, swap ${s0}MB used (limit +${SWAP_GROW_MB}MB), jobs ${JOBS}"
  setsid bash -c "$CMD" & pid=$!
  lc=$c; lm=$m; hs=$s0; reason=""; rc=0
  while kill -0 "$pid" 2>/dev/null; do
    c=$(c_gb); m=$(mem_mb); s=$(swap_mb)
    [ "$c" -lt "$lc" ] && lc=$c; [ "$m" -lt "$lm" ] && lm=$m; [ "$s" -gt "$hs" ] && hs=$s
    if   [ "$c" -lt "$FLOOR_GB" ]; then reason=disk; why="C: down to ${c}G"
    elif [ "$m" -lt "$MEM_FLOOR_MB" ]; then reason=memory; why="MemAvailable down to ${m}MB"
    elif [ $((s - s0)) -gt "$SWAP_GROW_MB" ]; then reason=memory; why="swap up $((s - s0))MB since start (${s}MB used)"
    elif [ "$s" -gt "$SWAP_CAP_MB" ]; then reason=memory; why="swap nearly full (${s}MB used, cap ${SWAP_CAP_MB}MB)"
    fi
    if [ -n "$reason" ]; then
      echo "guard: $why, killing the command"
      kill -TERM -- -"$pid" 2>/dev/null; sleep 2; kill -KILL -- -"$pid" 2>/dev/null
      wait "$pid" 2>/dev/null; rc=98; return
    fi
    sleep 1
  done
  wait "$pid"; rc=$?
}

# setsid puts the command in its own session, so a Ctrl-C, hangup or tool timeout that
# stops the guard must take the command down with it.
trap '[ -n "$pid" ] && { kill -TERM -- -"$pid" 2>/dev/null; sleep 2; kill -KILL -- -"$pid" 2>/dev/null; }; status killed by a signal; exit 98' INT TERM HUP
wait_for_memory "before start" || { status not-started memory stayed low; exit 99; }
c=$(c_gb)
[ "$c" -lt "$START_GB" ] && { echo "guard: C: ${c}G free, below ${START_GB}G; not starting"; status not-started C: below ${START_GB}G; exit 99; }
attempt=0
while :; do
  run_once
  [ "$reason" = memory ] && [ "$attempt" -lt "$RETRIES" ] || break
  attempt=$((attempt+1))
  wait_for_memory "after a memory kill" || { status killed memory; exit 98; }
  c=$(c_gb)
  [ "$c" -lt "$START_GB" ] && { echo "guard: C: ${c}G free, below ${START_GB}G; not retrying"; status killed then C: low; exit 98; }
  echo "guard: retry $attempt of $RETRIES"
done
[ -n "$reason" ] && { status killed "$reason"; exit 98; }
echo "guard: done rc=$rc; lows C: ${lc}G, mem ${lm}MB avail; swap high ${hs}MB"
exit $rc
