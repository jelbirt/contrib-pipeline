# Unit checks: the two run modes. autonomous works what the scout finds; pause saves the scout's
# list and works none of it; --pick works named candidates from that list, in order, and never scouts.
# Usage: python3 -I unit_pause.py <contrib-run>.
import atexit, json, os, shutil, subprocess, sys, tempfile, threading, importlib.machinery, importlib.util
from pathlib import Path
from types import SimpleNamespace
t = Path(tempfile.mkdtemp(prefix="contrib-unit-pause-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
os.environ["CONTRIB_PROFILE_DIR"] = str(t / "profiles")
ld = importlib.machinery.SourceFileLoader("cr", sys.argv[1])
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)

LEDGER = t / "ledger"
(LEDGER / "candidates").mkdir(parents=True)
(LEDGER / "rejects.md").write_text("# Rejected candidates\n\n")
REPO = "own/repo"
SAVED = LEDGER / "repos" / "own-repo" / "scouted.json"

# ----- the profile key and the flag ------------------------------------------------------------
base = {"REPO_DIR": str(t / "clone"), "UPSTREAM_REMOTE": "upstream", "BASE_BRANCH": "main", "CONTRIBUTOR": "me"}
check("a profile without RUN_MODE is usable", m.profile_problems(base, base_only=True) == [])
check("RUN_MODE=pause and RUN_MODE=autonomous are usable",
      all(m.profile_problems({**base, "RUN_MODE": v}, base_only=True) == [] for v in ("pause", "autonomous")))
check("any other RUN_MODE is refused, by name",
      m.profile_problems({**base, "RUN_MODE": "manual"}, base_only=True)
      == ["RUN_MODE is 'manual': it is autonomous or pause"])

pdir = t / "profiles"; pdir.mkdir()
cargo = {"GUARD": "/bin/true", "YAML_DIR": "y", "SERVER_BUILD": "b", "SERVER_BIN": "s", "RUNNER_BUILD": "b",
         "RUNNER_BIN": "r"}
(pdir / "own-repo.md").write_text("# own/repo\n")
def mode_of(prof_mode, flag):
    lines = [f"{k}={v}" for k, v in {**base, **cargo}.items()] + ([f"RUN_MODE={prof_mode}"] if prof_mode else [])
    (pdir / "own-repo.env").write_text("\n".join(lines) + "\n")
    d = m.Driver(SimpleNamespace(repo=REPO, hours=1, commit_ledger=None, mode=flag))
    d.lockf.close(); d.logf.close()
    return d.run_mode
check("no RUN_MODE and no flag: autonomous, as runs were before", mode_of(None, None) == "autonomous")
check("the profile's RUN_MODE=pause is read", mode_of("pause", None) == "pause")
check("--mode autonomous overrides the profile's pause", mode_of("pause", "autonomous") == "autonomous")
check("--mode pause overrides a profile with no RUN_MODE", mode_of(None, "pause") == "pause")

# ----- the run loop, with the scout and the stages stubbed --------------------------------------
def driver(mode="autonomous", pick=None, limit=3, scouted=(), cap=None):
    d = m.Driver.__new__(m.Driver)
    d.repo, d.run_mode, d.repo_dir, d.upstream = REPO, mode, t / "clone", "upstream/main"
    d.run_id = "run-1"; d.run_dir = t / "runs" / "run-1"; d.run_dir.mkdir(parents=True, exist_ok=True)
    d.prof = {"MAX_OPEN": "10"}
    d.args = SimpleNamespace(approve_profile=None, learn=False, commit_ledger=None, retest=None, answer=None,
                             resume=False, issue_less=False, topic="", limit=limit, pick=pick)
    d.answer_cand, d.picks, d.scouted, d.done = None, None, None, []
    d.stop_kind = d.stop_reason = None
    d.t_start = m.time.time()
    d.lock, d.current = threading.RLock(), {}
    d.logs, d.scouts, d.worked = [], [], []
    d.log = lambda msg, *a, **k: d.logs.append(msg)
    d.watchdog = lambda: None
    d.preflight = lambda: None
    d.ledger_commit = lambda msg: None
    d.shutdown = lambda: True
    d.git = lambda *a, **k: "f" * 40
    d.all_states = lambda: [{"_dir": str(p)} for p in sorted((LEDGER / "candidates").iterdir())]
    def open_count():
        return (0, 10) if cap is not None and len(d.done) >= cap else (0, 0)
    d.open_count = open_count
    def scout():
        d.scouts.append(1)
        return [dict(c) for c in scouted]
    d.scout = scout
    def work(c, resume_dir=None):
        d.worked.append(c["slug"])
        d.done.append((c["slug"], "ready"))
    d.work_candidate = work
    return d

FOUND = [
    {"slug": "Fix_Thing", "title": "Fix the `thing`", "source": "issue #5", "issue": 5, "why": "it [breaks](x)",
     "size": "S", "confidence": "high", "files": ["a/b.rs", "c|d.rs"], "assign_comment": "may I take this?"},
    {"slug": "fix-thing", "title": "Second", "source": "gap: g", "issue": None, "why": "w", "size": "M"},
    {"slug": "taken", "title": "Third", "source": "gap: t", "why": "w"},
    {"slug": "", "title": "Fourth", "source": "gap: f", "why": "w"},
]
(LEDGER / "candidates" / "taken").mkdir()

d = driver("autonomous", scouted=FOUND, limit=2)
check("autonomous: the run ends done", d.main() == m.EXIT_DONE)
check("autonomous: the scout's candidates are worked in its order, up to the limit",
      d.worked == ["Fix_Thing", "fix-thing"] and len(d.scouts) == 1)
check("autonomous: no list is saved", not SAVED.exists())

d = driver("pause", scouted=FOUND)
check("pause: the run ends done (exit 0)", d.main() == m.EXIT_DONE)
check("pause: nothing is worked", d.worked == [] and len(d.scouts) == 1)
saved = json.loads(SAVED.read_text()) if SAVED.exists() else {}
slugs = [c["slug"] for c in saved.get("candidates", [])]
check("pause: the list is saved with the folder names the candidates will get",
      slugs == ["fix-thing", "fix-thing-2", "taken-2", "cand-4"])
check("pause: the list records its run, time and base", saved.get("run") == "run-1" and saved.get("repo") == REPO
      and saved.get("base_sha") == "f" * 40 and saved.get("scouted"))
check("pause: the stop reason says how many wait", d.stop_reason == "pause mode: 4 scouted candidates wait for your pick")
check("pause: the scout's other fields are kept", saved["candidates"][0]["files"] == ["a/b.rs", "c|d.rs"]
      and saved["candidates"][0]["assign_comment"] == "may I take this?")

d.write_summary()
summary = (d.run_dir / "SUMMARY.md").read_text()
check("pause: SUMMARY.md leads with the pause", "**Scouted 4 candidates and paused for your pick.**" in summary)
check("pause: SUMMARY.md lists the candidates and the pick command",
      "| Fix the \\`thing\\` | `fix-thing` | #5 | S | high |" in summary
      and "`contrib-run --repo own/repo --pick SLUG [SLUG ...]`" in summary)

q = "\n".join(d.scouted_lines())
check("QUEUE.md: a section with the count", q.startswith("## Scouted, waiting for your pick (4)"))
check("QUEUE.md: the pick command for the repo", "`contrib-run --repo own/repo --pick SLUG [SLUG ...]`" in q)
check("QUEUE.md: each entry has its slug, issue, size and confidence",
      "1. **Fix the \\`thing\\`** (`fix-thing`): issue #5, size S, confidence high" in q
      and "2. **Second** (`fix-thing-2`): no issue, size M" in q)
check("QUEUE.md: session text is made markdown-inert", "   - Why: it \\[breaks\\](x)" in q
      and "   - Files: a/b.rs, c\\|d.rs" in q)
check("QUEUE.md: the assignment request draft is shown",
      "Work waits until the issue is assigned to you. The scout's draft request: \"may I take this?\"" in q)
d.rebuild_queue(["> banner"])
queue = (LEDGER / "QUEUE.md").read_text()
check("QUEUE.md: the section comes right after the banner",
      queue.startswith("# Queue\n\n> banner\n\n## Scouted, waiting for your pick (4)"))

bad = LEDGER / "repos" / "other-repo"; bad.mkdir(parents=True)
(bad / "scouted.json").write_text(json.dumps({"repo": "own/repo", "candidates": [{"slug": "x", "title": "X"}]}))
check("QUEUE.md: a list whose repo does not match its folder is not shown",
      d.scouted_lines()[0] == "## Scouted, waiting for your pick (4)")
shutil.rmtree(bad)

d = driver("pause", scouted=[])
check("pause: a scout that finds nothing stops soft", d.main() == m.EXIT_SOFT)
check("pause: and the saved list is left as it was", len(json.loads(SAVED.read_text())["candidates"]) == 4)

# ----- --pick ----------------------------------------------------------------------------------
def refused(pick):
    d = driver(pick=pick)
    rc = d.main()
    return rc == 2 and d.worked == [] and d.scouts == []
check("pick: a slug not on the list is refused", refused(["nope"]))
check("pick: a slug named twice is refused", refused(["cand-4", "cand-4"]))
(LEDGER / "candidates" / "taken-2").mkdir()
check("pick: a slug a later run took is refused", refused(["taken-2"]))
(LEDGER / "candidates" / "taken-2").rmdir()

d = driver(pick=["cand-4", "fix-thing"])
check("pick: the run ends done", d.main() == m.EXIT_DONE)
check("pick: the picked ones are worked in the order given, with no scout",
      d.worked == ["cand-4", "fix-thing"] and d.scouts == [])
check("pick: the limit is the number picked", d.run_limit() == 2)
check("pick: the stop reason names the picks", d.stop_reason == "the picked candidates are done (2)")
check("pick: the picked ones leave the list, the rest stay",
      [c["slug"] for c in json.loads(SAVED.read_text())["candidates"]] == ["fix-thing-2", "taken-2"])
check("pick: the worked candidate is the saved one, fields and all", d.picks[1]["files"] == ["a/b.rs", "c|d.rs"])

d = driver(pick=["taken-2", "fix-thing-2"], cap=1)
check("pick: the open-PR cap still stops the run", d.main() == m.EXIT_SOFT and d.worked == ["taken-2"])
check("pick: a pick the run did not reach stays on the list",
      [c["slug"] for c in json.loads(SAVED.read_text())["candidates"]] == ["fix-thing-2"])

d = driver(pick=["fix-thing-2"])
check("pick: the last one empties the list", d.main() == m.EXIT_DONE
      and json.loads(SAVED.read_text())["candidates"] == [])
check("QUEUE.md: an empty list shows no section", d.scouted_lines() == [])
check("pick: an empty list is refused, saying how to make one", refused(["fix-thing-2"]))

# ----- the command line --------------------------------------------------------------------------
h = subprocess.run([sys.executable, "-I", sys.argv[1], "--help"], capture_output=True, text=True)
check("--mode and --pick are on the command line", "--mode {autonomous,pause}" in h.stdout and "--pick SLUG" in h.stdout)
for extra in (["--resume"], ["--issue-less"], ["--topic", "x"], ["--answer", "s", "t"]):
    a = subprocess.run([sys.executable, "-I", sys.argv[1], "--repo", REPO, "--pick", "a", *extra],
                       capture_output=True, text=True)
    check(f"--pick is refused with {extra[0]}", a.returncode == 2 and "--pick works only the candidates it names" in a.stderr)
a = subprocess.run([sys.executable, "-I", sys.argv[1], "--repo", REPO, "--mode", "manual"], capture_output=True, text=True)
check("--mode refuses a mode it does not know", a.returncode == 2 and "invalid choice" in a.stderr)

print("UNIT PAUSE " + ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
