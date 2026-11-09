# Unit checks for round 10: gh --jq refused, gh env allowlisted, git_dir_check refuses redirects.
import os, sys, tempfile, subprocess, importlib.machinery, importlib.util
from pathlib import Path
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
t = Path(tempfile.mkdtemp())
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
print("ALL PASS" if ok else "SOME FAILED")
