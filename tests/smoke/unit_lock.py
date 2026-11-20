# Unit checks: the run lock lasts a run and names its repo; the ledger write lock lasts a commit.
# So a publish of one repo can go on while another repo's run holds the run lock: contrib-push
# reads the holder's repo, and --commit-ledger takes only the ledger write lock.
# Usage: python3 -I unit_lock.py <contrib-run>.
import atexit, fcntl, json, os, shutil, subprocess, sys, tempfile, time, importlib.machinery, importlib.util
from pathlib import Path
from types import SimpleNamespace
t = Path(tempfile.mkdtemp(prefix="contrib-unit-lock-"))
atexit.register(shutil.rmtree, t, True)
ENV = {"CONTRIB_WORK": str(t / "work"), "CONTRIB_LEDGER": str(t / "ledger"), "CONTRIB_PROFILE_DIR": str(t / "profiles")}
os.environ.update(ENV)
RUN = os.path.realpath(sys.argv[1])
ld = importlib.machinery.SourceFileLoader("cr", RUN)
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)

LEDGER = t / "ledger"
LEDGER.mkdir()
ID = ["-c", "user.name=u", "-c", "user.email=u@l", "-c", "commit.gpgsign=false"]
def git(*a):
    return subprocess.run(["git", *ID, "-C", str(LEDGER), *a], capture_output=True, text=True).stdout.strip()
git("init", "-q")
# The driver commits with plain git, so the ledger repo needs its own
# identity: a CI runner has no global one.
git("config", "user.name", "u"); git("config", "user.email", "u@l")
git("config", "commit.gpgsign", "false")
(LEDGER / ".gitignore").write_text("*.lock\n")
git("add", "-A"); git("commit", "-qm", "start")
REPO, OTHER = "own/repo", "other/repo"
pdir = t / "profiles"; pdir.mkdir()
(pdir / "own-repo.md").write_text("# own/repo\n")
(pdir / "own-repo.env").write_text(
    f"REPO_DIR={t / 'clone'}\nUPSTREAM_REMOTE=upstream\nBASE_BRANCH=main\nCONTRIBUTOR=me\nGUARD=/bin/true\n"
    "YAML_DIR=y\nSERVER_BUILD=b\nSERVER_BIN=s\nRUNNER_BUILD=b\nRUNNER_BIN=r\n")

def driver(commit_ledger=None):
    return m.Driver(SimpleNamespace(repo=REPO, hours=1, commit_ledger=commit_ledger, mode=None))

def holder():
    """The repo on the lock file's first line, the one contrib-push reads."""
    first = ((LEDGER / ".run.lock").read_text().splitlines() or ["{}"])[0]
    return json.loads(first or "{}").get("repo")

# ----- the run lock names its repo, and a contender does not empty that line -------------------
(LEDGER / ".run.lock").write_text(json.dumps({"repo": OTHER, "pid": 1}) + "\n")   # an ended run's line
d = driver()
check("a run's lock file names its repo, on its only line",
      holder() == REPO and len((LEDGER / ".run.lock").read_text().splitlines()) == 1)
try:
    driver()
    busy = None
except SystemExit as e:
    busy = e.code
check("a second run is refused while the first holds the run lock (exit 40)", busy == m.EXIT_BUSY)
check("the refused run left the holder's line in place", holder() == REPO)
d.lockf.close(); d.logf.close()

# ----- --commit-ledger takes only the ledger write lock ----------------------------------------
c = driver(commit_ledger="publish x")
check("a --commit-ledger driver takes no run lock", c.lockf is None)
if c.lockf is not None:
    c.lockf.close()   # else the flock below waits on this process's own lock and the test hangs
c.logf.close()
with open(LEDGER / ".run.lock", "w") as f:
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    f.write(json.dumps({"repo": OTHER, "pid": 1}) + "\n"); f.flush()
    (LEDGER / "published.txt").write_text("x\n")
    r = subprocess.run([sys.executable, "-I", RUN, "--repo", REPO, "--commit-ledger", "publish c1"],
                       capture_output=True, text=True, env=dict(os.environ, **ENV), timeout=120)
    check(f"--commit-ledger commits while another repo's run holds the run lock (rc {r.returncode})",
          r.returncode == 0 and git("log", "-1", "--format=%s") == "publish c1"
          and "published.txt" in git("ls-files"))

# ----- the ledger write lock: held for a commit only, and a busy lock skips with False ----------
c = driver(commit_ledger="x")
m.LEDGER_LOCK_WAIT = 1
(LEDGER / "later.txt").write_text("y\n")
with open(LEDGER / ".ledger.lock", "a") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    t0 = time.time()
    res = c.ledger_commit("while busy")
    waited = time.time() - t0
check(f"a busy ledger write lock: the commit waits, then skips and says False ({waited:.1f}s)",
      res is False and 0.9 <= waited < 10 and git("log", "-1", "--format=%s") != "while busy")
check("the skip is logged", "ledger write lock stayed busy" in (LEDGER / "runs" / f"{c.run_id}.log").read_text())
res = c.ledger_commit("after")
check("once free, the commit lands and says True", res is True and git("log", "-1", "--format=%s") == "after"
      and "later.txt" in git("ls-files"))
with open(LEDGER / ".ledger.lock", "a") as f:
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        free = True
    except OSError:
        free = False
check("the ledger write lock is free again after the commit", free)

# ----- a git failure is a failed commit, not a silent one ---------------------------------------
c.ensure_ledger_ignores = lambda: None   # it fails first on a held index; this checks the commit's own checks
(LEDGER / "blocked.txt").write_text("z\n")
(LEDGER / ".git" / "index.lock").write_text("")
res = c.ledger_commit("blocked")
(LEDGER / ".git" / "index.lock").unlink()
check("git add failing (a held index) makes the commit say False and log it",
      res is False and "ledger commit failed" in (LEDGER / "runs" / f"{c.run_id}.log").read_text()
      and git("log", "-1", "--format=%s") != "blocked")
check("nothing left to commit is still a success", c.ledger_commit("again") is True
      and c.ledger_commit("nothing new") is True and git("log", "-1", "--format=%s") == "again")
c.logf.close()

print("UNIT LOCK " + ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
