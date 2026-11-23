# Unit checks: the crates a cargo-mode build downloads are those of the base the tree sits on.
# A retest after contrib-publish's rebase, or with --merge, builds on a newer upstream commit
# whose Cargo.lock may name crates the recorded base did not; fetching only for the recorded
# base left them out, and the offline build failed ("failed to download ... --offline").
# Usage: python3 -I unit_crates.py <contrib-run>. Everything lives in a new temp folder.
import atexit, json, os, shutil, sys, tempfile, importlib.machinery, importlib.util
from pathlib import Path
from types import SimpleNamespace
t = Path(tempfile.mkdtemp(prefix="contrib-unit-crates-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
os.environ["CONTRIB_PROFILE_DIR"] = str(t / "profiles")
ld = importlib.machinery.SourceFileLoader("cr", sys.argv[1])
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)

LEDGER, WORK = t / "ledger", t / "work"
REPO, SLUG = "own/repo", "fix-thing"
OLD, NEW, SAME, FORK, HEAD = ("a" * 40, "b" * 40, "c" * 40, "d" * 40, "e" * 40)
# Cargo.lock blob ids per commit: SAME keeps OLD's lockfile, NEW and FORK changed it.
LOCKS = {OLD: "1" * 40, NEW: "2" * 40, SAME: "1" * 40, FORK: "3" * 40}

cand = LEDGER / "candidates" / SLUG
(cand / "results").mkdir(parents=True)
(cand / "results" / "index.jsonl").write_text("")
(cand / "state.json").write_text(json.dumps({"slug": SLUG, "repo": REPO, "branch": "fix/thing", "base_sha": OLD}))
(WORK / "clones").mkdir(parents=True)

def lock_git(*a, check=True, cwd=None):
    if a[:3] == ("rev-parse", "--verify", "--quiet") and a[3].endswith(":engine/Cargo.lock"):
        return LOCKS.get(a[3].split(":")[0], "")
    return ""

def driver():
    d = m.Driver.__new__(m.Driver)
    d.repo, d.repo_dir, d.upstream, d.commands = REPO, t / "clone", "upstream/main", False
    d.prof = {"CRATE_ROOT": "engine", "UPSTREAM_REMOTE": "upstream", "BASE_BRANCH": "main"}
    d.args = SimpleNamespace(stub=True, real_requests=False)
    d.cand = cand                        # setup_base left unset, as a real Driver has it
    d.git = lock_git
    d.jail = lambda inner, **kw: ["jail", inner]
    d.fetches = []
    d.guarded = lambda rid, argv, retries=1: (d.fetches.append(rid), (0, ""))[1]
    d.log = lambda *a, **k: None
    return d

stamp = WORK / "cargo-home" / ".fetched-locks"
def stamped():
    return stamp.read_text().split() if stamp.is_file() else []

# --- ensure_fetched: which base's Cargo.lock it fetches for ---------------------------------
d = driver()
check("setup_base never set (a normal run)", "setup_base" not in vars(d))
check("no setup base: fetches for the recorded base", d.ensure_fetched("r1") == 0 and d.fetches == ["r1-fetch"])
check("no setup base: the recorded base's lockfile is stamped", stamped() == [LOCKS[OLD]])
d.fetches.clear()
check("the same lockfile again: no second fetch", d.ensure_fetched("r2") == 0 and d.fetches == [])
d.setup_base = NEW
check("a rebased base with a newer lockfile: fetches again", d.ensure_fetched("r3") == 0 and d.fetches == ["r3-fetch"])
check("the newer lockfile is stamped too", stamped() == [LOCKS[OLD], LOCKS[NEW]])
d.fetches.clear(); d.setup_base = SAME
check("a rebased base with the same lockfile: no fetch", d.ensure_fetched("r4") == 0 and d.fetches == [])
d.setup_base = "not-a-commit"
try:
    d.ensure_fetched("r5"); raised = False
except RuntimeError:
    raised = True
check("a setup base that is not a commit id is refused", raised)
d.setup_base, d.cand = None, None
try:
    d.ensure_fetched("r6"); raised = False
except RuntimeError:
    raised = True
check("no setup base and no candidate is refused, not a crash", raised)

# --- retest: the base it hands to the fetch, in cargo mode ----------------------------------
real_which = m.shutil.which
m.shutil.which = lambda name: "/usr/bin/" + name   # CI runners need not have bwrap or socat
def retest(fork_pt, merge):
    d = driver()
    seen = {}
    def git(*a, check=True, cwd=None):
        if a[:2] == ("rev-parse", d.upstream):
            return NEW
        if a[:3] == ("rev-parse", "--verify", "--quiet"):
            return HEAD
        if a[0] == "merge-base":
            return fork_pt
        return ""
    d.git = git
    d.replay_tests = lambda skip_gone=True: [{"kind": "test", "crate": "xerj-api"}]
    d.clone = lambda: WORK / "clones" / SLUG
    d.make_clone = lambda *a, **k: None
    d.cgit = lambda *a, **k: HEAD
    d.changed_crates = lambda fp: set()
    def clean_runs(reqs, head):
        seen["setup_base"], seen["kinds"] = d.setup_base, [q["kind"] for q in reqs]
        return []
    d.clean_runs = clean_runs
    d.node_stop = d.sweep = d.drop_copy = lambda *a, **k: None
    d.target_dir, d.bins = (lambda: t / "tgt"), (lambda: t / "bins")
    d.state = lambda **kw: seen.update(state=kw)
    rc = d.retest(SLUG, merge)
    return rc, seen
try:
    rc, seen = retest(FORK, False)
    check("cargo retest after a rebase: fetches for the new fork point", seen.get("setup_base") == FORK)
    check("cargo retest after a rebase: still runs fmt, the tests, clippy and the YAML suite",
          seen.get("kinds") == ["fmt", "test", "clippy", "yaml"])
    rc, seen = retest(OLD, False)
    check("cargo retest, not rebased: fetches for the recorded base", seen.get("setup_base") == OLD)
    rc, seen = retest(FORK, True)
    check("cargo retest with --merge: fetches for the base it merged", seen.get("setup_base") == NEW
          and seen.get("state", {}).get("retest", {}).get("merged_with") == NEW)
finally:
    m.shutil.which = real_which

print("UNIT CRATES " + ("PASS" if ok else "FAIL")); sys.exit(0 if ok else 1)
