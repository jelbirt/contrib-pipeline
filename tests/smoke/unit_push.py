# Unit checks for contrib-push (SPEC phase 3): the publish path on local fake repos, offline. The
# "fork" is a bare repo on disk, gh is a stub that logs its arguments, and contrib-run is a stub
# that records the ledger commit; contrib-check is the real one. Each guard has a mutant: the script
# with only that guard taken out, which its check must fail.
# Run as the other unit files are: python3 -I unit_push.py <path to contrib-run>.
import atexit, fcntl, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
t = Path(tempfile.mkdtemp(prefix="contrib-unit-push-"))
atexit.register(shutil.rmtree, t, True)
BIN_DIR = Path(os.path.realpath(sys.argv[1])).parent
PUSH, CHECK = BIN_DIR / "contrib-push", BIN_DIR / "contrib-check"
SRC = PUSH.read_text()
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)


ID = ["-c", "user.name=u", "-c", "user.email=u@l", "-c", "commit.gpgsign=false"]
def git(*a, cwd=None, check=True):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(r.stderr)
    return r.stdout.strip()


STUBS = t / "bin"; STUBS.mkdir()
GHLOG = t / "gh.log"
(STUBS / "gh").write_text(f"""#!/bin/sh
printf '%s\\n' "$*" >> {GHLOG}
case "$1 $2" in
  "pr create") echo "https://github.com/p-org/p/pull/7" ;;
  "repo sync") ;;
  *) echo '[]' ;;
esac
""")
(STUBS / "gh").chmod(0o755)
RUNLOG = t / "run.log"
RUNSTUB = t / "run-stub"
RUNSTUB.write_text(f"import sys\nopen({str(RUNLOG)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n")
PROFILES = t / "profiles"; PROFILES.mkdir()
LEDGER = t / "ledger"
n = 0


def world(status="ready", fork_has_other=False, base_moves=False, owner="me", gated=True, **state):
    """upstream, the pipeline clone with fix/<slug>, a bare fork, the user's checkout of it, a
    profile and a ready candidate whose final gate passed on the tip (unless gated=False).
    Returns (slug, the branch tip, the paths)."""
    global n
    n += 1
    slug = f"c{n}"
    w = t / f"w{n}"
    up, pipe, user = w / "up", w / "pipe", w / "user"
    fork = w / owner / "p.git"
    git("init", "-q", "-b", "main", str(up))
    for f, text in (("pkg/a.py", "a = 1\n"), ("pkg/b.py", "b = 1\n"), ("docs/d.md", "d\n")):
        (up / f).parent.mkdir(parents=True, exist_ok=True); (up / f).write_text(text)
    git("add", "-A", cwd=up); git(*ID, "commit", "-qm", "base", cwd=up)
    base = git("rev-parse", "HEAD", cwd=up)
    git("clone", "-q", "-o", "upstream", str(up), str(pipe))
    git("checkout", "-q", "-b", f"fix/{slug}", cwd=pipe)
    (pipe / "pkg/a.py").write_text("a = 2\n"); git("add", "-A", cwd=pipe); git(*ID, "commit", "-qm", "fix", cwd=pipe)
    tip = git("rev-parse", "HEAD", cwd=pipe)
    git("clone", "-q", "--bare", str(up), str(fork))
    if fork_has_other:
        other = w / "other"
        git("clone", "-q", str(fork), str(other))
        git("checkout", "-q", "-b", f"fix/{slug}", cwd=other)
        (other / "x").write_text("x\n"); git("add", "-A", cwd=other); git(*ID, "commit", "-qm", "other", cwd=other)
        git("push", "-q", "origin", f"fix/{slug}", cwd=other)
    git("clone", "-q", str(fork), str(user))
    if base_moves:
        (up / "pkg/b.py").write_text("b = 2\n"); git("add", "-A", cwd=up); git(*ID, "commit", "-qm", "moved", cwd=up)
    (PROFILES / "p-org-p.env").write_text(
        f"REPO=p-org/p\nREPO_DIR={pipe}\nUSER_REPO_DIR={user}\nUPSTREAM_REMOTE=upstream\nBASE_BRANCH=main\n"
        "CONTRIBUTOR=me\nSENSITIVE_PATHS=^\\.github/\nAREAS=^(pkg)/ ^(docs)/\n")
    cand = LEDGER / "candidates" / slug; cand.mkdir(parents=True)
    (cand / "state.json").write_text(json.dumps({"repo": "p-org/p", "branch": f"fix/{slug}", "base_sha": base,
                                                 "issue": None, "status": status,
                                                 **({"gate": {"ok": True, "head": tip}} if gated else {}), **state}))
    (cand / "pr-title.txt").write_text("Correct the a value\n")
    (cand / "pr-body.txt").write_text("## Change Summary\n\nA fix.\n")
    return slug, tip, {"up": up, "pipe": pipe, "user": user, "fork": fork, "cand": cand}


ENV = dict(os.environ, PATH=f"{STUBS}:{os.environ['PATH']}", CONTRIB_LEDGER=str(LEDGER),
           CONTRIB_PROFILE_DIR=str(PROFILES), CONTRIB_PUSH_CHECK=str(CHECK), CONTRIB_PUSH_RUN=str(RUNSTUB),
           GIT_CONFIG_NOSYSTEM="1")


def run(*args, src=None):
    for f in (GHLOG, RUNLOG):
        f.unlink(missing_ok=True)
    path = PUSH
    if src is not None:
        path = t / "contrib-push-mutant"; path.write_text(src)
    r = subprocess.run([sys.executable, "-I", str(path), *args], capture_output=True, text=True, env=ENV)
    gh = GHLOG.read_text() if GHLOG.exists() else ""
    return r.returncode, r.stdout + r.stderr, gh


def set_state(p, **kv):
    st = json.loads((p["cand"] / "state.json").read_text())
    st.update(kv)
    (p["cand"] / "state.json").write_text(json.dumps(st))


def base_now(p):
    git("fetch", "-q", "upstream", cwd=p["pipe"])
    return git("rev-parse", "refs/remotes/upstream/main", cwd=p["pipe"])


def fork_branch(p, slug):
    return git("--git-dir", str(p["fork"]), "rev-parse", "--verify", "--quiet", f"refs/heads/fix/{slug}", check=False)


def opened(gh):
    return any(l.startswith("pr create") for l in gh.splitlines())


# --- the happy path, and each stop -------------------------------------------------------------
def t_ok(src=None):
    slug, tip, p = world()
    rc, out, gh = run(slug, tip, src=src)
    st = json.loads((p["cand"] / "state.json").read_text())
    create = [l for l in gh.splitlines() if l.startswith("pr create")]
    return (rc == 0 and "PR https://github.com/p-org/p/pull/7" in out and fork_branch(p, slug) == tip
            and st.get("status") == "published" and st.get("pr", "").endswith("/pull/7")
            and st.get("published_head") == tip and len(create) == 1
            and "--repo p-org/p" in create[0] and f"--head me:fix/{slug}" in create[0]
            and f"--body-file {p['cand'] / 'pr-body.txt'}" in create[0]
            and RUNLOG.exists() and "--commit-ledger publish " + slug in RUNLOG.read_text()
            and not git("for-each-ref", "refs/contrib-publish", cwd=p["user"]))


def t_moved(src=None):
    slug, tip, p = world()
    git(*ID, "commit", "-q", "--allow-empty", "-m", "later", cwd=p["pipe"])
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "moved after approval" in out and not opened(gh) and not fork_branch(p, slug)


def t_no_force(src=None):
    slug, tip, p = world(fork_has_other=True)
    before = fork_branch(p, slug)
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "STOP" in out and not opened(gh) and fork_branch(p, slug) == before


def t_published(src=None):
    slug, tip, p = world(status="published", pr="https://github.com/p-org/p/pull/1")
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "already published" in out and not opened(gh) and not fork_branch(p, slug)


def t_not_ready(src=None):
    slug, tip, p = world(status="needs-you")
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "not ready" in out and not opened(gh) and not fork_branch(p, slug)


def t_verdict(src=None):
    """The base changed the branch's area since: no push without a passing retest of the merge."""
    slug, tip, p = world(base_moves=True)
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "retest-merge" in out and not opened(gh) and not fork_branch(p, slug)


def t_verdict_retested(src=None):
    slug, tip, p = world(base_moves=True)
    git("fetch", "-q", "upstream", cwd=p["pipe"])
    base_now = git("rev-parse", "refs/remotes/upstream/main", cwd=p["pipe"])
    st = json.loads((p["cand"] / "state.json").read_text())
    st["retest"] = {"ok": True, "head": tip, "merged_with": base_now}
    (p["cand"] / "state.json").write_text(json.dumps(st))
    rc, out, gh = run(slug, tip, src=src)
    return rc == 0 and opened(gh) and fork_branch(p, slug) == tip


def t_retest_stale(src=None):
    """A passing retest merged with an older base does not count."""
    slug, tip, p = world(base_moves=True)
    st = json.loads((p["cand"] / "state.json").read_text())
    st["retest"] = {"ok": True, "head": tip, "merged_with": st["base_sha"]}
    (p["cand"] / "state.json").write_text(json.dumps(st))
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and not opened(gh) and not fork_branch(p, slug)


def t_title(src=None):
    slug, tip, p = world()
    (p["cand"] / "pr-title.txt").write_text("")
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "pr-title.txt" in out and not opened(gh) and not fork_branch(p, slug)


def t_lock(src=None):
    slug, tip, p = world()
    LEDGER.mkdir(exist_ok=True)
    with open(LEDGER / ".run.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "ledger lock" in out and not opened(gh) and not fork_branch(p, slug)


def held_by(repo, slug, tip, src):
    """Run contrib-push while the run lock is held by a run that names repo, as contrib-run does."""
    LEDGER.mkdir(exist_ok=True)
    with open(LEDGER / ".run.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps({"repo": repo, "pid": 1}) + "\n"); f.flush()
        return run(slug, tip, src=src)


def t_lock_other(src=None):
    """A run of another repo holds the run lock: this repo's publish goes on."""
    slug, tip, p = world()
    rc, out, gh = held_by("q-org/q", slug, tip, src)
    return rc == 0 and opened(gh) and fork_branch(p, slug) == tip and "does not touch p-org/p" in out


def t_lock_same(src=None):
    """A run of this repo (any letter case) holds it: refused, nothing opened."""
    slug, tip, p = world()
    rc, out, gh = held_by("P-org/P", slug, tip, src)
    return rc == 1 and "of P-org/P holds the ledger lock" in out and not opened(gh) and not fork_branch(p, slug)


def t_fork_ci(src=None):
    slug, tip, p = world()
    rc, out, gh = run("--fork-ci", slug, tip, src=src)
    st = json.loads((p["cand"] / "state.json").read_text())
    create = [l for l in gh.splitlines() if l.startswith("pr create")]
    return (rc == 0 and "FORK-CI https://" in out and fork_branch(p, slug) == tip and st.get("status") == "ready"
            and "repo sync me/p --branch main" in gh and len(create) == 1 and "--repo me/p" in create[0]
            and "--draft" in create[0] and not RUNLOG.exists())


def t_fork_owner(src=None):
    slug, tip, p = world(owner="someone")
    rc, out, gh = run("--fork-ci", slug, tip, src=src)
    return rc == 1 and "not a fork owned by me" in out and not opened(gh) and not fork_branch(p, slug)


def t_owner_publish(src=None):
    """A normal publish checks the fork's owner too: nothing goes to someone else's repo."""
    slug, tip, p = world(owner="someone")
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "not a fork owned by me" in out and not opened(gh) and not fork_branch(p, slug)


def t_ungated(src=None):
    """No passing gate or retest of this commit is recorded: nothing goes out."""
    slug, tip, p = world(gated=False)
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "no passing final gate or retest" in out and not opened(gh) and not fork_branch(p, slug)


def t_gate_other_head(src=None):
    """A gate that passed on another commit (before a rebase or a follow-up commit) does not count."""
    slug, tip, p = world(gated=False, gate={"ok": True, "head": "0" * 40})
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and not opened(gh) and not fork_branch(p, slug)


def t_gate_failed(src=None):
    slug, tip, p = world(gated=False)
    set_state(p, gate={"ok": False, "head": tip})
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and not opened(gh) and not fork_branch(p, slug)


def t_retest_covers(src=None):
    """A passing retest of this commit stands in for the gate (after a rebase, say)."""
    slug, tip, p = world(gated=False)
    set_state(p, retest={"ok": True, "head": tip, "merged_with": ""})
    rc, out, gh = run(slug, tip, src=src)
    return rc == 0 and opened(gh) and fork_branch(p, slug) == tip


def t_fork_ci_ungated(src=None):
    slug, tip, p = world(gated=False)
    rc, out, gh = run("--fork-ci", slug, tip, src=src)
    return rc == 1 and not opened(gh) and not fork_branch(p, slug)


def t_has_pr(src=None):
    """Status still ready but a PR recorded (a publish whose ledger step failed): no second PR."""
    slug, tip, p = world(pr="https://github.com/p-org/p/pull/1")
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and "already published" in out and not opened(gh) and not fork_branch(p, slug)


def t_retest_failed(src=None):
    slug, tip, p = world(base_moves=True)
    set_state(p, retest={"ok": False, "head": tip, "merged_with": base_now(p)})
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and not opened(gh) and not fork_branch(p, slug)


def t_retest_other_head(src=None):
    slug, tip, p = world(base_moves=True)
    set_state(p, retest={"ok": True, "head": "0" * 40, "merged_with": base_now(p)})
    rc, out, gh = run(slug, tip, src=src)
    return rc == 1 and not opened(gh) and not fork_branch(p, slug)


def t_record_fails(src=None):
    """The PR is open but state.json cannot be written: the URL and what to do still print, exit 0."""
    slug, tip, p = world()
    (p["cand"] / "state.json.tmp").mkdir()
    rc, out, gh = run(slug, tip, src=src)
    return rc == 0 and opened(gh) and "PR https://github.com/p-org/p/pull/7" in out and "not updated" in out


CHECKS = [t_ok, t_moved, t_no_force, t_published, t_not_ready, t_verdict, t_verdict_retested,
          t_retest_stale, t_title, t_lock, t_lock_other, t_lock_same, t_fork_ci, t_fork_owner, t_owner_publish, t_ungated,
          t_gate_other_head, t_gate_failed, t_retest_covers, t_fork_ci_ungated, t_has_pr,
          t_retest_failed, t_retest_other_head, t_record_fails]
for c in CHECKS:
    try:
        check(c.__name__[2:], c())
    except Exception as e:
        check(f"{c.__name__[2:]} ({type(e).__name__}: {e})", False)

rc, out, gh = run("c1", "abc")
check("rev_must_be_full", rc == 2 and "40-character" in out and not gh)
rc, out, gh = run("../c1", "a" * 40)
check("slug_checked", rc == 2 and "bad slug" in out and not gh)

MUTANTS = [
    (t_moved, "        if got != rev:\n", "        if False:\n"),
    (t_no_force, 'f"{rev}:refs/heads/{branch}")', 'f"+{rev}:refs/heads/{branch}")'),
    (t_has_pr, 'if s.get("status") == "published" or s.get("pr"):', 'if s.get("status") == "published":'),
    (t_owner_publish, '        fork = fork_name(w)          # both modes', '        fork = "me/p"          # both modes'),
    (t_ungated, '        if not covered:\n', '        if False:\n'),
    (t_gate_other_head, 'r.get("head") == rev for r in', 'True for r in'),
    (t_gate_failed, 'r.get("ok") is True and r.get("head") == rev for r in', 'r.get("head") == rev for r in'),
    (t_retest_failed, 'rt.get("ok") is True and rt.get("head") == rev and', 'rt.get("head") == rev and'),
    (t_retest_other_head, 'rt.get("ok") is True and rt.get("head") == rev and', 'rt.get("ok") is True and'),
    (t_record_fails, '    except Exception as e:      # the PR is open', '    except ZeroDivisionError as e:      # the PR is open'),
    (t_not_ready, 'if s.get("status") != "ready":', "if False:"),
    (t_verdict, "        gate_check(w, s, rev)\n", "\n"),
    (t_retest_stale, ' and rt.get("merged_with") == base_now:', ":"),
    (t_title, 'if not title or "\\n" in title or len(title) > 200:', "if False:"),
    (t_lock, '        ledger_free(w["REPO"])\n', "\n"),
    (t_lock_same, "if holder and holder.lower() != repo.lower():", "if holder:"),
    (t_lock_other, "if holder and holder.lower() != repo.lower():", "if False:"),
    (t_fork_owner, "if not m or m.group(1).lower() != w[\"CONTRIBUTOR\"].lower():", "if not m:"),
]
for c, old, new in MUTANTS:
    if SRC.count(old) != 1:
        check(f"mutant for {c.__name__[2:]}: its guard's text is in contrib-push once (found {SRC.count(old)})", False)
        continue
    try:
        caught = not c(src=SRC.replace(old, new))
    except Exception:
        caught = True
    check(f"without its guard, {c.__name__[2:]} fails", caught)
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
