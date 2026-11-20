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
    d.cand = None
    def open_count():
        return (0, 10) if cap is not None and len(d.done) >= cap else (0, 0)
    d.open_count = open_count
    def scout():
        d.scouts.append(1)
        return [dict(c) for c in scouted]
    d.scout = scout
    def work(c, resume_dir=None, pick=False):   # the real one unlists a pick once its state is written
        slug = Path(resume_dir).name if resume_dir else c["slug"]
        if pick:
            d.unlist(slug)
        d.worked.append(slug)
        d.done.append((slug, "ready"))
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
check("pause: the banner says how to pick",
      d.pick_lines() == ["> Pick from the scouted list below with `contrib-run --repo own/repo --pick SLUG [SLUG ...]`."])
check("pause: the scout's other fields are kept", saved["candidates"][0]["files"] == ["a/b.rs", "c|d.rs"]
      and saved["candidates"][0]["assign_comment"] == "may I take this?")

keep = SAVED.read_text()
(m.WORK / "clones" / "clone-held").mkdir(parents=True)
check("pause: a name a clone in the work folder holds is not saved",
      [c["slug"] for c in d.save_scouted([{"slug": "clone-held", "title": "x"}])["candidates"]] == ["clone-held-2"])
(m.WORK / "clones" / "clone-held").rmdir(); SAVED.write_text(keep)

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
(m.WORK / "clones" / "taken-2").mkdir(parents=True)
check("pick: a slug whose clone a later run made is refused", refused(["taken-2"]))
(m.WORK / "clones" / "taken-2").rmdir()

d = driver(pick=["cand-4", "fix-thing"])
check("pick: the run ends done", d.main() == m.EXIT_DONE)
check("pick: the picked ones are worked in the order given, with no scout",
      d.worked == ["cand-4", "fix-thing"] and d.scouts == [])
check("pick: the limit is the number picked", d.run_limit() == 2)
check("pick: the stop reason names the picks", d.stop_reason == "the picked candidates are done (2)")
check("pick: with every pick reached, the banner adds no pick line", d.pick_lines() == [])
check("pick: the picked ones leave the list, the rest stay",
      [c["slug"] for c in json.loads(SAVED.read_text())["candidates"]] == ["fix-thing-2", "taken-2"])
check("pick: the worked candidate is the saved one, fields and all", d.picks[1]["files"] == ["a/b.rs", "c|d.rs"])

d = driver(pick=["taken-2", "fix-thing-2"], cap=1)
check("pick: the open-PR cap still stops the run", d.main() == m.EXIT_SOFT and d.worked == ["taken-2"])
check("pick: a pick the run did not reach stays on the list",
      [c["slug"] for c in json.loads(SAVED.read_text())["candidates"]] == ["fix-thing-2"])
check("pick: and the banner names it with a ready --pick command",
      d.pick_lines() == ["> Picks this run did not reach, still on the list: "
                         "`contrib-run --repo own/repo --pick fix-thing-2`."])

d = driver(pick=["fix-thing-2"])
check("pick: the last one empties the list", d.main() == m.EXIT_DONE
      and json.loads(SAVED.read_text())["candidates"] == [])
check("QUEUE.md: an empty list shows no section", d.scouted_lines() == [])
check("pick: an empty list is refused, saying how to make one", refused(["fix-thing-2"]))

def listed():
    return [c["slug"] for c in json.loads(SAVED.read_text())["candidates"]]
def save_list(*cands):
    SAVED.write_text(json.dumps({"repo": REPO, "run": "run-0", "scouted": "t", "candidates": list(cands)}))
def put_state(slug, **st):
    (LEDGER / "candidates" / slug).mkdir(parents=True, exist_ok=True)
    (LEDGER / "candidates" / slug / "state.json").write_text(json.dumps({"repo": REPO, **st}))

# The real work_candidate: an error before the ledger holds the pick leaves it on the list, with no folder.
save_list({"slug": "real-a", "title": "A", "issue": "x"}, {"slug": "real-b", "title": "B", "issue": 7})
d = driver(pick=["real-b"]); del d.work_candidate
def git_fails(*a, **k):
    raise RuntimeError("no upstream")
d.git = git_fails
check("pick: an error before the candidate is in the ledger stops the run hard", d.main() == m.EXIT_HARD)
check("pick: and the pick stays on the list, with no folder squatting its name",
      listed() == ["real-a", "real-b"] and not (LEDGER / "candidates" / "real-b").exists())

# The real work_candidate: a pick leaves the list once its state is written.
d = driver(pick=["real-a"]); del d.work_candidate
d.assign_first = True                     # an unreadable issue is then dropped right after the state write
d.reject = lambda *a, **k: None
d.finish = lambda status, **k: d.done.append(("real-a", status))
check("pick: the real work_candidate runs the pick", d.main() == m.EXIT_DONE and d.done == [("real-a", "abandoned")])
check("pick: it leaves the list only with its state written",
      listed() == ["real-b"] and json.loads((LEDGER / "candidates" / "real-a" / "state.json").read_text())["status"] == "running")
check("pick: its state says it was picked, so a resume of it never scouts",
      json.loads((LEDGER / "candidates" / "real-a" / "state.json").read_text()).get("picked") is True)

# An issue a later run took under another name.
put_state("issue-7-other", issue=7, status="ready")
check("pick: an issue already in the ledger under another name is refused", refused(["real-b"]))
check("QUEUE.md: and the list says so", "already in the ledger as issue-7-other, so a pick is refused" in "\n".join(d.scouted_lines()))
put_state("issue-7-other", repo="other/repo", issue=7, status="ready")
check("pick: the same number in another repo is not the same issue", m.Driver.pick_setup(d, ["real-b"])[0]["slug"] == "real-b")

# A resume in pause mode works the stopped candidates and does not scout over the list.
put_state("stopped-a", status="stopped")
before = SAVED.read_text()
d = driver("pause", scouted=FOUND); d.args.resume = True
check("pause: a resume ends done", d.main() == m.EXIT_DONE)
check("pause: a resume works the stopped candidates and does not scout",
      d.worked == ["stopped-a"] and d.scouts == [] and SAVED.read_text() == before)
check("pause: a resume's stop reason says it does not scout",
      d.stop_reason == "resumed 1 stopped candidate; a resume in pause mode or of a pick does not scout")
d = driver("autonomous", scouted=FOUND, limit=2); d.args.resume = True
check("autonomous: a resume still scouts after its stopped candidates",
      d.main() == m.EXIT_DONE and d.worked == ["stopped-a", "Fix_Thing"] and d.scouts == [1])
# After a --mode pause run on an autonomous profile, a stopped pick's --resume must not scout either.
put_state("stopped-p", status="stopped", picked=True)
d = driver("autonomous", scouted=FOUND, limit=3); d.args.resume = True
check("autonomous: a resume that finishes a picked candidate does not scout",
      d.main() == m.EXIT_DONE and d.worked == ["stopped-a", "stopped-p"] and d.scouts == [])
check("autonomous: and its stop reason says why",
      d.stop_reason == "resumed 2 stopped candidates; a resume in pause mode or of a pick does not scout")
shutil.rmtree(LEDGER / "candidates" / "stopped-a"); shutil.rmtree(LEDGER / "candidates" / "stopped-p")
# A stopped pick in another repo does not stop this repo's autonomous resume from scouting.
put_state("other-p", repo="other/repo", status="stopped", picked=True)
d = driver("autonomous", scouted=FOUND, limit=2); d.args.resume = True; d.main()
check("autonomous: another repo's stopped pick does not stop this repo's resume from scouting",
      d.resume_picks is False and d.scouts == [1])
shutil.rmtree(LEDGER / "candidates" / "other-p")

# The real scout(): the fields a pick is made on survive its filter (guards the merge with the probe work).
d = driver("pause"); del d.scout
d.run_dir = t / "runs" / "scout-real"; d.prof = {"MAX_OPEN": "10", "CONTRIBUTOR": "me"}; d.prof_md = ""
d.assign_first = False; d.args.scout_model = "sonnet"
d.check_stop = lambda *a, **k: None
d.snapshot = lambda dest: dest.mkdir(parents=True, exist_ok=True)
d.all_states = lambda: []
d.archive_transcripts = lambda home: None
d.session_tmp = lambda home, make=True: t / "tmp"
def scout_session(role, sdir, *a, **k):
    (sdir / "candidates.json").write_text(json.dumps([dict(FOUND[0], slug="real-scout")]))
    (sdir / "next.json").write_text(json.dumps({"action": "stage-done", "summary": "1 candidate"}))
    return {}
d.session = scout_session
got = d.scout()
check("scout: confidence and files survive its filter",
      len(got) == 1 and got[0].get("confidence") == "high" and got[0].get("files") == ["a/b.rs", "c|d.rs"])

# A stop asked for during the scout keeps its kind and reason; the list is still saved.
d = driver("pause", scouted=FOUND[:1])
plain = d.scout
def scout_then_stop():
    found = plain()
    d.request_stop("soft", "STOP file")
    return found
d.scout = scout_then_stop
check("pause: a stop asked for during the scout ends the run soft", d.main() == m.EXIT_SOFT)
check("pause: with the stop's own reason", d.stop_reason == "STOP file")
check("pause: and the list is still saved", json.loads(SAVED.read_text())["run"] == "run-1" and listed() == ["fix-thing"])

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
