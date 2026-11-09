# Unit checks: no driver git command starts an automatic gc or maintenance; preflight's repo_gc
# turns it off in the repository's own config, runs gc in the foreground when it is due, only
# logs a failed gc, refuses while another gc runs, and stops a gc that runs out of time with its
# children; a new candidate clone has automatic gc off.
import atexit, os, shutil, socket, sys, tempfile, time, subprocess, importlib.machinery, importlib.util
from pathlib import Path
t = Path(tempfile.mkdtemp(prefix="contrib-unit-gc-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
drv = sys.argv[1]
ld = importlib.machinery.SourceFileLoader("cr", drv)
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)
# Setup git: an identity, and gc off so only the command under test can start one.
SET = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "gc.auto=0", "-c", "maintenance.auto=false"]
def g(repo, *a):
    return subprocess.run(["git", *SET, "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout.strip()
def packs(repo):
    return len(list((Path(repo) / ".git" / "objects" / "pack").glob("pack-*.pack")))
src = t / "src"; g(t, "init", "-q", "-b", "main", str(src))
n = 0
def commit():
    global n
    n += 1; (src / "f").write_text(f"{n}\n"); g(src, "add", "f"); g(src, "commit", "-q", "-m", str(n))
def fetch_pack(repo):   # one new pack per fetch
    commit(); g(repo, "-c", "fetch.unpackLimit=1", "fetch", "-q", str(src), "+main:refs/heads/main")
dst = t / "dst"; g(t, "init", "-q", str(dst))
# The repository's own config would gc after any fetch, in the foreground so the control is not a race.
g(dst, "config", "gc.autoPackLimit", "2"); g(dst, "config", "gc.autoDetach", "false")
for _ in range(4):
    fetch_pack(dst)
check("setup made 4 packs", packs(dst) == 4)

ctl = t / "ctl"; shutil.copytree(dst, ctl, symlinks=True)
commit()
subprocess.run(["git", "-c", "fetch.unpackLimit=1", "-C", str(ctl), "fetch", "-q", str(src), "+main:refs/heads/main"],
               capture_output=True, check=True)
check(f"control: plain git fetch starts a gc (packs {packs(ctl)})", packs(ctl) == 1)

d = m.Driver.__new__(m.Driver)
d.repo_dir = dst; logs = []; d.log = logs.append
d.run_dir = t / "run"; d.run_dir.mkdir(); d.current = {}; d.started = set()
trace = t / "trace"
d.git("-c", "fetch.unpackLimit=1", "fetch", "-q", str(src), "+main:refs/heads/main", cwd=dst,
      env=dict(d.git_env(), GIT_TRACE=str(trace)))
check(f"driver git fetch starts no gc (packs {packs(dst)})", packs(dst) == 5)
check("driver git fetch starts no maintenance at all", "maintenance" not in trace.read_text())

# repo_gc: below git's limits nothing happens; above them gc runs before the call returns.
d.repo_gc(dst)
check("repo_gc leaves a repository with few packs alone", packs(dst) == 5 and not logs)
check("repo_gc turns automatic gc off in the repository's own config",
      g(dst, "config", "gc.auto") == "0" and g(dst, "config", "maintenance.auto") == "false")
while packs(dst) <= 51:   # still over git's limit of 50 after the broken copy loses one
    fetch_pack(dst)
bad = t / "bad"; shutil.copytree(dst, bad, symlinks=True)
# The driver's own gc.auto=0, without the repository's: a direct gc --auto does nothing (the
# repository says foreground, so a gc that did run would be finished before the check).
g(dst, "config", "--unset", "gc.auto")
d.git("gc", "--auto", "--quiet", cwd=dst)
check(f"driver git gc --auto does nothing (packs {packs(dst)})", packs(dst) > 50)
# repo_gc keeps gc in the foreground whatever the repository says.
g(dst, "config", "gc.autoDetach", "true")
d.repo_gc(dst)
check(f"repo_gc packs a repository over the limit, in the foreground (packs {packs(dst)})",
      packs(dst) == 1 and not (dst / ".git" / "gc.pid").exists() and not logs)
check("repo_gc leaves no gc output file", not list(d.run_dir.glob("gc-*")))
# A repository missing objects (the pipeline clone was once a copy of a partial clone): logged, not raised.
first = min((bad / ".git" / "objects" / "pack").glob("pack-*.pack"), key=lambda p: p.stat().st_mtime_ns)
for p in first.parent.glob(first.stem + ".*"):
    p.unlink()
try:
    d.repo_gc(bad); raised = False
except Exception:
    raised = True
check("repo_gc logs a failed gc and does not raise", not raised and len(logs) == 1 and "gc in" in logs[0] and "failed" in logs[0])
d.repo_gc(t / "nothing-here")
check("repo_gc skips a folder that is not a repository", len(logs) == 1)

# A gc already running (gc.pid names a live process on this host) stops the run; a stale one does not.
pidf = dst / ".git" / "gc.pid"
pidf.write_text(f"{os.getpid()} {socket.gethostname()}")
try:
    d.repo_gc(dst); live_refused = False
except RuntimeError as e:
    live_refused = "running" in str(e)
gone = subprocess.Popen(["true"]); gone.wait()
pidf.write_text(f"{gone.pid} {socket.gethostname()}")
try:
    d.repo_gc(dst); stale_ok = True
except RuntimeError:
    stale_ok = False
pidf.unlink(missing_ok=True)
check("repo_gc refuses while another gc is running", live_refused)
check("repo_gc ignores a stale gc.pid", stale_ok)

# A gc that runs out of time is stopped with its children, and the run stops too. A stand-in
# git starts a child and hangs on "gc"; everything else goes to the real git.
fake = t / "fakebin"; fake.mkdir(); kid = t / "kid.pid"
(fake / "git").write_text(f'#!/bin/sh\nfor a in "$@"; do [ "$a" = gc ] && {{ sleep 60 & echo $! > {kid}; sleep 60; exit 0; }}; done\n'
                          f'exec {shutil.which("git")} "$@"\n')
(fake / "git").chmod(0o755)
path0 = os.environ["PATH"]; os.environ["PATH"] = f"{fake}:{path0}"
t0 = time.time()
try:
    d.repo_gc(dst, timeout=2); stopped = False
except RuntimeError as e:
    stopped = "did not finish" in str(e)
finally:
    os.environ["PATH"] = path0
kpid = int(kid.read_text()) if kid.exists() else 0
for _ in range(30):
    try:
        os.kill(kpid, 0); time.sleep(0.1)
    except ProcessLookupError:
        kpid = 0; break
check(f"repo_gc stops a gc that runs out of time, and raises ({time.time() - t0:.0f} s)", stopped and time.time() - t0 < 20)
check("the timed-out gc's child is gone too", kid.exists() and kpid == 0)

# A candidate clone: automatic gc off in its own config, so a session's commit cannot start one.
new = t / "newclone"
d.clone = lambda: new; d.upstream = "upstream/main"; d.wip_refs = lambda slug: []
d.make_clone("x", "fix/x", g(dst, "rev-parse", "main"), restore=False)
check("new clone has gc.auto 0", g(new, "config", "gc.auto") == "0")
check("new clone has maintenance.auto false", g(new, "config", "maintenance.auto") == "false")
print("ALL PASS" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
