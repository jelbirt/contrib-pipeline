# Unit checks for round 10: gh --jq refused, gh env allowlisted, git_dir_check refuses redirects.
import atexit, os, shutil, sys, tempfile, subprocess, importlib.machinery, importlib.util
from pathlib import Path
# The driver works in a new temp folder (git_dir_check copies .git under WORK/snap); removed at exit.
t = Path(tempfile.mkdtemp(prefix="contrib-unit-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
drv = sys.argv[1]
ld = importlib.machinery.SourceFileLoader("cr", drv)
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)
repo = "xerj-org/xerj"
check("api --jq refused", m.gh_argv(["api", "repos/xerj-org/xerj/issues/1", "--jq", "env.X"], repo)[0] is None)
check("issue list --jq refused", m.gh_argv(["issue", "list", "--jq", ".[]"], repo)[0] is None)
check("issue list -q refused", m.gh_argv(["issue", "list", "-q", ".[]"], repo)[0] is None)
check("api GET still allowed", m.gh_argv(["api", "repos/xerj-org/xerj/issues/1"], repo)[0] is not None)
os.environ["SECRET_TEST_VAR"] = "x"
check("gh env drops other vars", "SECRET_TEST_VAR" not in m.Driver.gh_env() and "PATH" in m.Driver.gh_env())
d = m.Driver.__new__(m.Driver)
class Cand: name = "t"
d.cand = Cand()
c = t / "clone"; subprocess.run(["git", "init", "-q", str(c)], check=True)
d.clone = lambda: c
# git_dir_check asks git (in the jail, during a run) where the git dir is; here plain host git.
d.cgit = lambda *a, check=True, **k: subprocess.run(["git", "-C", str(c), *a], capture_output=True, text=True).stdout.strip()
def refused():
    try:
        d.git_dir_check(); return False
    except RuntimeError:
        return True
check("plain clone accepted", not refused())
(c / ".git" / "commondir").write_text("/home/user/xerj/.git\n"); check("commondir refused", refused())
(c / ".git" / "commondir").unlink()
(c / ".git" / "objects" / "info" / "alternates").write_text("/home/user/xerj/.git/objects\n"); check("alternates refused", refused())
(c / ".git" / "objects" / "info" / "alternates").unlink()
os.symlink("/home/user/xerj/.git/refs/heads", c / ".git" / "refs" / "x"); check("symlinked ref folder refused", refused())
os.unlink(c / ".git" / "refs" / "x")
check("clean again accepted", not refused())
(c / ".git" / "objects" / "ab").mkdir(exist_ok=True); os.symlink("/home/user/xerj/.git/objects", c / ".git" / "objects" / "ab" / "x")
check("symlink deep in objects refused", refused()); os.unlink(c / ".git" / "objects" / "ab" / "x")
(c / ".git" / "HEAD").write_text("garbage\n"); (c / "HEAD").write_text("ref: refs/heads/main\n"); (c / "refs").mkdir(); (c / "objects").mkdir()
check("fake repository at the clone root refused", refused())
# stop_group with the leader's Popen reaps it: a zombie leader once kept its group "alive" for
# the whole 50 s grace and every time limit reported a survivor.
import signal, time
p = subprocess.Popen(["sleep", "60"], start_new_session=True); t0 = time.time()
check("stop_group reaps its own child at once", m.stop_group(p.pid, signal.SIGTERM, 20, proc=p) and time.time() - t0 < 5)
# node_stop stops the node and the bridge, each reaped, and clears the node.
p = subprocess.Popen(["sleep", "60"], start_new_session=True); b = subprocess.Popen(["sleep", "60"], start_new_session=True)
node = {"node": {"pid": p.pid, "bridge": b.pid, "dir": ""}}; d.node_procs = {p.pid: p, b.pid: b}
d.st = lambda: node; d.state = lambda **k: node.update(k); d.started = {p.pid, b.pid}; d.log = lambda *a: None
t0 = time.time(); gone = d.node_stop()
check("node_stop stops node and bridge quickly", gone and p.returncode is not None and b.returncode is not None
      and node["node"] is None and not d.started and time.time() - t0 < 5)
# A node that will not stop still leaves the bridge stopped, and the node kept in state.
calls = []; real = m.stop_group
m.stop_group = lambda pg, *a, **k: calls.append(pg) or pg != 111
node["node"] = {"pid": 111, "bridge": 222, "dir": ""}
try:
    check("node_stop still stops the bridge when the node survives",
          d.node_stop() is False and calls == [111, 222] and node["node"] is not None)
finally:
    m.stop_group = real
print("ALL PASS" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
