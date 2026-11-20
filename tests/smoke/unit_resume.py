# Unit checks: a run touches only its own repo's candidates. The ledger is shared by every repo,
# so --resume, stale recovery, the open-PR cap and --answer each check the candidate's repo:
# another repo's candidate has its own branches, pipeline clone and profile.
# Usage: python3 -I unit_resume.py <contrib-run>.
import atexit, json, os, shutil, sys, tempfile, threading, importlib.machinery, importlib.util
from pathlib import Path
from types import SimpleNamespace
t = Path(tempfile.mkdtemp(prefix="contrib-unit-resume-"))
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
(LEDGER / "candidates").mkdir(parents=True)
(WORK / "nodes").mkdir(parents=True); (WORK / "clones").mkdir()
REPO, OTHER = "own/repo", "other/repo"

def put_state(name, **kw):
    d = LEDGER / "candidates" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text(json.dumps({"slug": name, "repo": REPO, **kw}))
    return d
def state(name):
    return json.loads((LEDGER / "candidates" / name / "state.json").read_text())
def clear():
    for d in (LEDGER / "candidates").iterdir():
        shutil.rmtree(d)
    for d in (WORK / "clones").iterdir():
        shutil.rmtree(d)

def driver(limit=3):
    d = m.Driver.__new__(m.Driver)
    d.repo, d.run_mode, d.repo_dir, d.upstream = REPO, "autonomous", t / "clone", "upstream/main"
    d.run_id = "run-1"; d.run_dir = t / "runs" / "run-1"; d.run_dir.mkdir(parents=True, exist_ok=True)
    d.prof = {"MAX_OPEN": "10", "CONTRIBUTOR": "me"}
    d.args = SimpleNamespace(approve_profile=None, learn=False, commit_ledger=None, retest=None, answer=None,
                             resume=True, issue_less=False, topic="", limit=limit, pick=None, stub=True)
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
    d.open_count = lambda: (0, 0)
    def scout():
        d.scouts.append(1)
        return []
    d.scout = scout
    def work(c, resume_dir=None, pick=False):
        d.worked.append(Path(resume_dir).name if resume_dir else c["slug"])
        d.done.append((d.worked[-1], "ready"))
    d.work_candidate = work
    return d

# ----- --resume queues this repo's stopped candidates only --------------------------------------
put_state("own-a", status="stopped")
put_state("own-b", repo="Own/Repo", status="stopped")          # a repo name is not case-sensitive
put_state("other-a", repo=OTHER, status="stopped", picked=True)
before = (LEDGER / "candidates" / "other-a" / "state.json").read_text()
d = driver(); d.main()
check("resume: this repo's stopped candidates are worked, in ledger order", d.worked == ["own-a", "own-b"])
check("resume: another repo's stopped candidate is not worked, and its state is untouched",
      "other-a" not in d.worked and (LEDGER / "candidates" / "other-a" / "state.json").read_text() == before)
check("resume: the log names the repo whose stopped candidates were left alone",
      "resume: stopped candidates of other/repo are left alone; each repo's resume is its own --repo" in d.logs)
check("resume: another repo's stopped pick does not stop this resume from scouting",
      d.resume_picks is False and d.scouts == [1])
put_state("own-p", status="stopped", picked=True)
d = driver(); d.main()
check("resume: this repo's stopped pick does stop it from scouting", d.resume_picks is True and d.scouts == [])
clear()
put_state("other-a", repo=OTHER, status="stopped")
d = driver(); d.main()
check("resume: with only another repo's stopped candidates, nothing is resumed and the scout runs",
      d.worked == [] and d.scouts == [1])
clear()

# ----- the real work_candidate refuses another repo's folder before writing anything ------------
put_state("other-a", repo=OTHER, status="stopped")
before = (LEDGER / "candidates" / "other-a" / "state.json").read_text()
d = driver(); err = None
try:
    m.Driver.work_candidate(d, {}, resume_dir=str(LEDGER / "candidates" / "other-a"))
except RuntimeError as e:
    err = str(e)
check("work_candidate: a resume of another repo's candidate is refused, naming its repo",
      err == "other-a belongs to 'other/repo', not own/repo; resume it with --repo other/repo")
check("work_candidate: and nothing was written to it",
      (LEDGER / "candidates" / "other-a" / "state.json").read_text() == before and d.cand is None
      and not (LEDGER / "candidates" / "other-a" / "results").exists())
clear()

# ----- stale recovery saves only this repo's clones ---------------------------------------------
def stale_driver():
    d = driver()
    d.saved, d.swept = [], []
    d.save_clone = lambda: d.saved.append(d.cand.name) or "saved"
    d.sweep = lambda roots: d.swept.append([str(r) for r in roots])
    return d
for name, repo, status in (("own-run", REPO, "running"), ("oth-run", OTHER, "running"),
                           ("oth-run2", OTHER, "running"), ("own-stop", REPO, "stopped"),
                           ("oth-stop", OTHER, "stopped")):
    put_state(name, repo=repo, status=status)
for name in ("own-run", "oth-run", "own-stop", "oth-stop"):
    (WORK / "clones" / name).mkdir()
put_state("oth-run", repo=OTHER, status="running", node={"dir": str(WORK / "nodes" / "n1")})
(WORK / "nodes" / "n1").mkdir()
put_state("own-run-c", repo="Own/Repo", status="running")
oth_stop_before = (LEDGER / "candidates" / "oth-stop" / "state.json").read_text()
d = stale_driver(); m.Driver.recover_stale(d)
check("recover: this repo's stale and stopped clones are saved, no other",
      sorted(d.saved) == ["own-run", "own-run-c", "own-stop"])
check("recover: another repo's stale candidate is still stopped, with its own repo's resume command",
      state("oth-run")["status"] == "stopped" and state("oth-run")["resume"] == "contrib-run --repo other/repo --resume")
check("recover: and its clone is kept for that repo's next run, which saves it",
      state("oth-run")["cleanup"] == "clone kept for the next other/repo run to save"
      and (WORK / "clones" / "oth-run").is_dir())
check("recover: one with no clone says so", state("oth-run2")["cleanup"] == "no clone")
check("recover: another repo's stale candidate still has its jail processes stopped",
      [str(WORK / "clones" / "oth-run"), str(WORK / "bins" / "oth-run")] in d.swept
      and [str(WORK / "clones" / "oth-run2"), str(WORK / "bins" / "oth-run2")] in d.swept)
check("recover: this repo's stale candidate gets this repo's resume command",
      state("own-run")["status"] == "stopped" and state("own-run")["resume"] == "contrib-run --repo own/repo --resume"
      and state("own-run")["cleanup"] == "saved")
check("recover: another repo's stopped candidate is not touched",
      (LEDGER / "candidates" / "oth-stop" / "state.json").read_text() == oth_stop_before)
check("recover: another repo's stale candidate still has its node cleared",
      state("oth-run")["node"] is None and not (WORK / "nodes" / "n1").exists())
check("recover: this repo's resume command uses the run's spelling of the repo, which has the profile",
      state("own-run-c")["resume"] == "contrib-run --repo own/repo --resume")
d2 = stale_driver(); d2.repo = OTHER; m.Driver.recover_stale(d2)
check("recover: that repo's next run saves the clones this run left, and only those",
      sorted(d2.saved) == ["oth-run", "oth-stop"] and state("oth-run")["cleanup"] == "saved"
      and state("oth-stop")["cleanup"] == "saved")
check("recover: the log says whose stale candidate it recovered",
      "recovering stale candidate oth-run of other/repo" in d.logs and "recovering stale candidate own-run" in d.logs)
clear()

# ----- the open-PR cap counts this repo's ready packets, as it counts this repo's open PRs -------
put_state("own-r", status="ready"); put_state("own-r2", repo="OWN/REPO", status="ready")
put_state("oth-r", repo=OTHER, status="ready")
d = driver()
check("open_count: ready packets of another repo do not count against this repo's cap",
      m.Driver.open_count(d) == (0, 2))
clear()

# ----- --answer checks the repo before anything else --------------------------------------------
put_state("oth-q", repo=OTHER, status="needs-you", issue=12)
put_state("oth-s", repo=OTHER, status="stopped", answer_pending={"answer": "x"})
put_state("own-q", status="needs-you", issue=None)
d = driver(); d.assign_first = True; d.asked = []
d.is_assigned = lambda n: d.asked.append(n) or False
def answer(slug):
    try:
        return m.Driver.answer_setup(d, slug, "yes")
    except RuntimeError as e:
        return str(e)
check("answer: another repo's candidate is refused by name, with no issue read in the wrong repo",
      answer("oth-q") == "oth-q belongs to 'other/repo'; run --answer with --repo other/repo" and d.asked == [])
check("answer: the repo check comes before the stopped-with-an-answer message",
      answer("oth-s") == "oth-s belongs to 'other/repo'; run --answer with --repo other/repo")
r = answer("own-q")
check("answer: this repo's candidate is accepted", isinstance(r, tuple) and r[1] == "yes")
put_state("own-i", status="needs-you", issue=7)
check("answer: this repo's candidate still gets the assignment check",
      answer("own-i").startswith("issue #7 is not assigned to @me yet") and d.asked == [7])
clear()

# ----- QUEUE.md names each candidate's own repo in its commands ----------------------------------
put_state("oth-q", repo=OTHER, status="needs-you", question="which?", stage="A")
put_state("oth-s", repo=OTHER, status="stopped", resume="contrib-run --repo other/repo --resume --issue-less")
put_state("own-s", status="stopped")
put_state("odd-s", repo="other/repo; rm -rf x", status="stopped", resume="contrib-run --repo x/y --resume; rm")
d = driver(); m.Driver.rebuild_queue(d)
q = (LEDGER / "QUEUE.md").read_text()
check("QUEUE.md: another repo's needs-you candidate is answered with its own repo",
      "Answer with `contrib-run --repo other/repo --answer oth-q \"...\"`" in q and "--repo own/repo --answer" not in q)
check("QUEUE.md: a stopped candidate shows its own resume command",
      "Resume with `contrib-run --repo other/repo --resume --issue-less`" in q)
check("QUEUE.md: one with no resume command gets one built from its repo",
      "Resume with `contrib-run --repo own/repo --resume`" in q)
check("QUEUE.md: an odd repo or resume value is never copied into a command",
      "rm -rf" not in q and "; rm" not in q and q.count("Resume with `contrib-run --repo own/repo --resume`") == 2)

print("UNIT RESUME PASS" if ok else "UNIT RESUME FAIL")
sys.exit(0 if ok else 1)
