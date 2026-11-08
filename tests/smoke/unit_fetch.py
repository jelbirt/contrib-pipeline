# Unit checks for round 12: the driver saves a clone only from a checked, driver-owned copy.
# Usage: python3 -I unit_fetch.py <contrib-run>. Everything lives in a new temp folder.
import os, sys, signal, tempfile, subprocess, importlib.machinery, importlib.util
from pathlib import Path
t = Path(tempfile.mkdtemp(prefix="contrib-unit-fetch-"))
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
ld = importlib.machinery.SourceFileLoader("cr", sys.argv[1])
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)
def g(*a, cwd):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(cwd), *a],
                          capture_output=True, text=True)
victim = t / "victim"; g("init", "-q", str(victim), cwd=t); (victim / "s").write_text("secret\n")
g("add", "-A", cwd=victim); g("commit", "-qm", "secret", cwd=victim); g("branch", "private", cwd=victim)
pipe = t / "pipe"; g("init", "-q", str(pipe), cwd=t); g("commit", "-q", "--allow-empty", "-m", "base", cwd=pipe)
d = m.Driver.__new__(m.Driver); d.repo_dir = pipe
class Cand: name = "t"
d.cand = Cand()
c = t / "clone"
d.clone = lambda: c
d.cgit = lambda *a, check=True, **k: subprocess.run(["git", "-C", str(c), *a], capture_output=True, text=True, timeout=20).stdout.strip()
def fresh():
    subprocess.run(["rm", "-rf", str(c)]); g("clone", "-q", "--no-hardlinks", str(pipe), str(c), cwd=t)
    g("checkout", "-q", "-b", "fix/x", cwd=c); g("commit", "-q", "--allow-empty", "-m", "work", cwd=c)
def got():
    return g("for-each-ref", "--format=%(refname)", "refs/got", cwd=pipe).stdout.split()
def save():
    g("update-ref", "-d", "refs/got/fix/x", cwd=pipe)
    signal.alarm(60)
    try:
        d.fetch_from_clone("+refs/heads/*:refs/got/*"); return "ok"
    except RuntimeError as e:
        return "refused: " + str(e)[:90]
    finally:
        signal.alarm(0)
fresh(); r = save(); check(f"clean clone saves ({r})", r == "ok" and "refs/got/fix/x" in got())
check("copy folder removed afterwards", not (t / "work" / "snap" / "t").exists())
fresh(); (c / ".git" / "packed-refs").unlink(missing_ok=True); os.mkfifo(c / ".git" / "packed-refs"); r = save(); check(f"packed-refs FIFO refused, no hang ({r})", r.startswith("refused"))
fresh(); os.mkfifo(c / "inc"); g("config", "include.path", "../inc", cwd=c); r = save()
check(f"config include refused, no hang ({r})", r.startswith("refused"))
fresh(); dd = c / ".git" / "refs" / "heads" / "hid"; dd.mkdir(); os.chmod(dd, 0o300); r = save(); os.chmod(dd, 0o700)
check(f"unlistable folder refused ({r})", r.startswith("refused"))
fresh(); os.symlink(victim / ".git" / "refs" / "heads" / "private", c / ".git" / "refs" / "heads" / "p"); r = save()
check(f"symlinked ref refused ({r})", r.startswith("refused"))
fresh(); (c / ".git" / "HEAD").write_text("garbage\n"); (c / "HEAD").write_text("ref: refs/heads/master\n")
(c / "refs").mkdir(); (c / "objects").mkdir(); (c / "commondir").write_text(str(victim / ".git") + "\n"); r = save()
check(f"fake root repository refused ({r})", r.startswith("refused") and not any("private" in x for x in got()))
fresh(); g("config", "pack.threads", "64", cwd=c); g("config", "extensions.partialClone", "evil", cwd=c); r = save()
check(f"session config does not reach the host fetch ({r})", r == "ok" and "refs/got/fix/x" in got())
subprocess.run(["rm", "-rf", str(t)])
print("ALL PASS" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
