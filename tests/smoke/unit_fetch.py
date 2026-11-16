# Unit checks for rounds 12 to 14: the driver saves a clone only from a checked, driver-owned copy.
# Usage: python3 -I unit_fetch.py <contrib-run>. Everything lives in a new temp folder.
import atexit, os, shutil, sys, signal, tempfile, subprocess, importlib.machinery, importlib.util
from pathlib import Path
t = Path(tempfile.mkdtemp(prefix="contrib-unit-fetch-"))
def cleanup():          # runs even when a check raises; a test may leave a folder unlistable
    for root, dirs, _ in os.walk(t):
        for x in dirs:
            try:
                os.chmod(os.path.join(root, x), 0o700, follow_symlinks=False)
            except OSError:
                pass
    shutil.rmtree(t, ignore_errors=True)
atexit.register(cleanup)
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
def on_alarm(*_):
    raise TimeoutError("hang")
signal.signal(signal.SIGALRM, on_alarm)    # a hang fails its check; cleanup still runs
def save():
    g("update-ref", "-d", "refs/got/fix/x", cwd=pipe)
    signal.alarm(60)
    try:
        d.fetch_from_clone("+refs/heads/*:refs/got/*"); return "ok"
    except RuntimeError as e:
        return "refused: " + str(e)[:90]
    except TimeoutError:
        return "hang"
    finally:
        signal.alarm(0)
fresh(); r = save(); check(f"clean clone saves ({r})", r == "ok" and "refs/got/fix/x" in got())
check("copy folders removed afterwards", not any(os.path.lexists(t / "work" / "snap" / f"t.{u}") for u in ("save", "check")))
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
# A session process swaps a folder in .git for a symlink while the copy runs: listdir is wrapped
# so the swap lands right after the copy has listed .git and before it looks at refs.
outside = t / "outside"; outside.mkdir(); planted = outside / "planted"; planted.write_text("host\n")
snapp = t / "work" / "snap" / "t.save"
fresh(); real_listdir = os.listdir; swapped = []
def listdir_then_swap(p):
    names = real_listdir(p)
    if not swapped and "refs" in names and "objects" in names:
        swapped.append(1); (c / ".git" / "refs").rename(c / ".git" / "refs-real"); os.symlink(outside, c / ".git" / "refs")
    return names
os.listdir = listdir_then_swap
try:
    r = save()
finally:
    os.listdir = real_listdir
check(f"folder swapped for a symlink mid-copy refused ({r})", swapped and r.startswith("refused") and "symlink" in r)
check("nothing linked from the swapped-in folder, copy removed", os.stat(planted).st_nlink == 1 and not os.path.lexists(snapp))
fresh(); snapp.parent.mkdir(parents=True, exist_ok=True)
if os.path.lexists(snapp):
    os.unlink(snapp)
os.symlink(outside, snapp); r = save()
check(f"leftover snap symlink cleared, clean save ({r})", r == "ok" and "refs/got/fix/x" in got())
check("nothing copied through a leftover snap symlink", sorted(outside.iterdir()) == [planted] and not os.path.lexists(snapp))
# The copy itself never follows a symlink, even one the check before it did not see (a folder
# swapped mid-copy): call it directly on a clone whose .git/refs points at another repository.
fresh(); dest = t / "work" / "snap" / "direct"; d.remove_snap(dest)
subprocess.run(["rm", "-rf", str(c / ".git" / "refs")]); os.symlink(victim / ".git" / "refs", c / ".git" / "refs")
try:
    d.copy_git_dir(c, dest); r = "ok"
except RuntimeError as e:
    r = "refused: " + str(e)[:90]
linked = [p for p in dest.rglob("*") if p.is_file() and not p.is_symlink()
          and os.lstat(p).st_ino == os.lstat(victim / ".git" / "refs" / "heads" / "private").st_ino] if dest.exists() else []
check(f"copy refuses a symlinked folder by itself ({r})", r.startswith("refused") and not linked)
d.remove_snap(dest); check("refused copy removable", not os.path.lexists(dest))
# A read-only folder in the session's .git: the copy's folders are the driver's own (0700), so
# the copy is still removed and the next save still works.
fresh(); os.chmod(c / ".git" / "refs" / "heads", 0o555); r1 = save(); r2 = save(); os.chmod(c / ".git" / "refs" / "heads", 0o755)
check(f"read-only folder: saves twice ({r1}, {r2})", r1 == "ok" and r2 == "ok" and not os.path.lexists(snapp))
# A build's jail binds the checked copy, not the live .git: bwrap resolves a bind's source when
# the jail starts, and a .git swapped by then for `..` would bind the folder above the clone.
# Control first: the old bind of the live path shows the marker; then the real cargo_jail.
(t / "marker").write_text("above the clone\n")
d.prof = {}; d.target_dir = lambda: t / "work" / "targets" / "t"; d.engine_dir = lambda: c
def run_jail(argv):
    gd = c / ".git"; gd.rename(c / "git-real"); os.symlink("..", gd)
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(gd); (c / "git-real").rename(gd)
if shutil.which("bwrap"):
    fresh(); old = run_jail(d.jail(f"cat {t}/marker", rw=(c,), over=((c / ".git", c / ".git"),)))
    fresh(); argv = d.cargo_jail(f"cat {t}/marker")
    src = [argv[i + 1] for i in range(len(argv) - 2) if argv[i] == "--ro-bind" and argv[i + 2] == str(c / ".git")]
    new = run_jail(argv)
    check(f"control: binding the live path shows the marker (rc {old.returncode})", "above the clone" in old.stdout)
    check(f"build jail binds the checked copy ({src})", src == [str(t / "work" / "snap" / "t.build")])
    # With the destination swapped, bwrap 0.9 refuses to start the jail; the bound source is the
    # protection (checked above), this only shows nothing leaks either way.
    check(f"build jail with a swapped .git shows nothing (rc {new.returncode})", "above the clone" not in new.stdout and new.returncode != 0)
    fresh(); ok_git = subprocess.run(d.cargo_jail(f"git -C {c} rev-parse HEAD"), capture_output=True, text=True, timeout=60)
    head = g("rev-parse", "HEAD", cwd=c).stdout.strip()
    check(f"git in a build jail reads the bound copy (rc {ok_git.returncode})", ok_git.stdout.strip() == head)
elif os.environ.get("CONTRIB_REQUIRE_BWRAP"):
    check("bwrap is installed (CONTRIB_REQUIRE_BWRAP is set)", False)
else:
    print("SKIP build jail checks: bwrap is not installed")
print("ALL PASS" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
