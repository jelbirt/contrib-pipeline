# Unit checks: --lead, a bug the user hands over directly. The run works that one candidate from the
# user's description and never scouts; stage A verifies it; --issue links it to an issue, and the
# assignment-first check then applies as for any issue candidate.
# Usage: python3 -I unit_lead.py <contrib-run>.
import atexit, json, os, shutil, subprocess, sys, tempfile, threading, importlib.machinery, importlib.util
from pathlib import Path
from types import SimpleNamespace
t = Path(tempfile.mkdtemp(prefix="contrib-unit-lead-"))
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
def in_ledger(slug, **st):
    (LEDGER / "candidates" / slug).mkdir(parents=True, exist_ok=True)
    (LEDGER / "candidates" / slug / "state.json").write_text(json.dumps(st))
in_ledger("old-42", repo=REPO, issue=42, status="ready")
in_ledger("other-43", repo="else/where", issue=43, status="ready")

def driver(mode="autonomous", lead=None, issue=None, slug=None, limit=3):
    d = m.Driver.__new__(m.Driver)
    d.repo, d.run_mode, d.repo_dir, d.upstream = REPO, mode, t / "clone", "upstream/main"
    d.run_id = "run-1"; d.run_dir = t / "runs" / "run-1"; d.run_dir.mkdir(parents=True, exist_ok=True)
    d.prof = {"MAX_OPEN": "10"}
    d.args = SimpleNamespace(approve_profile=None, learn=False, commit_ledger=None, retest=None, answer=None,
                             resume=False, issue_less=False, topic="", limit=limit, pick=None,
                             lead=lead, issue=issue, slug=slug)
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
    def scout():                          # finds one candidate, then nothing: a stray scout cannot loop
        d.scouts.append(1)
        return [{"slug": "scouted-one", "title": "S", "why": "w"}] if len(d.scouts) == 1 else []
    d.scout = scout
    def work(c, resume_dir=None, pick=False):
        d.worked.append(dict(c))
        d.done.append((c["slug"], "ready"))
    d.work_candidate = work
    return d

# ----- lead_setup: the candidate built from the user's words --------------------------------------
TEXT = ("ImportString: a path starting with '.' raises TypeError, not ValidationError\n"
        "_import_string_logic in pydantic/_internal/_validators.py catches ImportError only.")
d = driver()
c = d.lead_setup(TEXT)
check("the slug comes from the lead's first words", c["slug"] == "importstring-a-path-starting-with-raises-typeerr")
check("the title is the first line; the why is the whole text",
      c["title"] == TEXT.splitlines()[0] and c["why"] == TEXT)
check("it is marked as the user's lead, issue-less, with no probe",
      c["lead"] is True and c["issue"] is None and c["probe"] is None and c["source"] == "the user, with --lead")
check("--slug names it", d.lead_setup(TEXT, slug="Import String Dot")["slug"] == "import-string-dot")
check("--issue links it to that issue", d.lead_setup(TEXT, issue=77)["issue"] == 77)
check("an issue another repo's candidate has is free here", d.lead_setup(TEXT, issue=43)["issue"] == 43)
def refused(*a, **k):
    try:
        d.lead_setup(*a, **k)
    except RuntimeError as e:
        return str(e)
    return None
check("an empty lead is refused", "empty" in (refused("") or "") and "empty" in (refused("  \n ") or ""))
check("a lead over the size cap is refused", "keep it under" in (refused("x" * (m.LEAD_MAX_CHARS + 1)) or ""))
check("a lead at the size cap is kept", refused("x" * m.LEAD_MAX_CHARS) is None)
check("a slug with no letters or digits is refused", "no usable name" in (refused(TEXT, slug="!!") or "")
      and "no usable name" in (refused("!! ??") or ""))
check("an explicit --slug that is taken is refused, not renamed", "--slug old-42 is taken" in (refused(TEXT, slug="old-42") or ""))
check("issue numbers that are not issue numbers are refused",
      all("not an issue number" in (refused(TEXT, issue=n) or "") for n in (0, -3, 10 ** 9)))
check("an issue this repo's ledger already holds is refused, by its folder",
      "already in the ledger as old-42" in (refused(TEXT, issue=42) or ""))

# ----- the run loop -------------------------------------------------------------------------------
for mode in ("autonomous", "pause"):
    d = driver(mode, lead=TEXT, limit=3)
    rc = d.main()
    check(f"{mode}: a --lead run works the lead, ends done, and never scouts",
          rc == m.EXIT_DONE and [w["slug"] for w in d.worked] == [c["slug"]] and d.scouts == [])
    check(f"{mode}: the run ends with the lead's own reason", d.stop_reason == "the candidate you described with --lead is done")
d = driver(lead=TEXT, limit=3)
d.work_candidate = lambda c, resume_dir=None, pick=False: d.worked.append(dict(c))
check("even a lead that does not count as done never brings the scout in", d.main() == m.EXIT_DONE and d.scouts == [])
d = driver(lead=TEXT, limit=3)
d.lead = d.lead_setup(TEXT)
check("a lead run's limit is 1, whatever --limit says", d.run_limit() == 1)
check("without a lead the limit is --limit", driver(limit=3).run_limit() == 3)
d = driver(lead="   ")
check("a refused lead ends the run with exit 2 before any work", d.main() == 2 and d.worked == [] and d.scouts == [])
d = driver(lead=TEXT, issue=42)
check("so does an issue the ledger already holds", d.main() == 2 and d.worked == [])

# ----- the real work_candidate: the lead is written to the ledger as the user's ------------------
class Halt(Exception):
    pass
def real(issue=None, slug="lead-real"):
    d = driver(lead=TEXT, issue=issue, slug=slug); del d.work_candidate
    d.assign_first = True
    d.rejected, d.asked = [], []
    d.reject = lambda *a, **k: d.rejected.append(a)
    d.assignment_stop = lambda n, c: d.asked.append(n) or d.finish("needs-you", asked_by="assign")
    d.finish = lambda status, **k: d.done.append((slug, status))
    def snap(dest):
        raise m.StopRun()
    d.snapshot = snap
    d.main()
    return d, json.loads((LEDGER / "candidates" / slug / "state.json").read_text())
d, st = real()
check("an issue-less lead passes assignment first without a reject or an assignment check",
      d.rejected == [] and d.asked == [] and st["status"] == "running")
check("the ledger records it as the user's lead",
      st["candidate"]["lead"] is True and st["source"] == "the user, with --lead" and st["issue"] is None
      and st["title"] == TEXT.splitlines()[0])
check("the run notes the lead is in the ledger, so a stop makes it a --resume", d.lead_written is True)
d, st = real(issue=77, slug="lead-issue")
check("a lead with --issue gets the usual assignment-first check, on that issue",
      d.asked == [77] and st["issue"] == 77 and d.done == [("lead-issue", "needs-you")])

# ----- a lead the run never reached, and a stopped lead resumed ------------------------------------
d = driver(lead=TEXT); d.lead = d.lead_setup(TEXT)
check("a lead not yet in the ledger: the banner says to run the same --lead again",
      any("The lead was not started" in x for x in d.pick_lines()))
d.lead_written = True
check("once in the ledger it says nothing more (a stop gives the --resume line)",
      not any("lead" in x for x in d.pick_lines()))
in_ledger("stopped-lead", repo=REPO, status="stopped", issue=None,
          candidate={"slug": "stopped-lead", "title": "T", "why": "w", "lead": True})
for mode in ("autonomous", "pause"):
    d = driver(mode, limit=3); d.args.resume = True
    def resumed(c, resume_dir=None, pick=False):
        slug = Path(resume_dir).name if resume_dir else c["slug"]
        d.worked.append({"slug": slug}); d.done.append((slug, "ready"))
    d.work_candidate = resumed
    rc = d.main()
    check(f"{mode}: a --resume that finishes a stopped lead works it and never scouts",
          rc == m.EXIT_DONE and [w["slug"] for w in d.worked] == ["stopped-lead"] and d.scouts == [])
(LEDGER / "candidates" / "stopped-lead" / "state.json").unlink()

# ----- the assignment stop names no scout draft for a lead ----------------------------------------
d = driver(); d.prof = {"CONTRIBUTOR": "me", "MAX_OPEN": "10"}
d.issue_assignees = lambda n: []
d.finish = lambda status, **k: dict(k, status=status)
for name, c, text, ask in (("lead", {"lead": True}, "no draft: this came from --lead", "no scout ran"),
                           ("scouted", {"assign_comment": ""}, "the scout drafted no comment", "Post the comment drafted")):
    d.cand = t / "assign" / name; (d.cand / "session").mkdir(parents=True)
    r = d.assignment_stop(5, c)
    check(f"assignment stop, {name}: the draft file and the question fit where it came from",
          r["status"] == "needs-you" and text in (d.cand / "session" / "assign-comment.md").read_text()
          and ask in r["question"])

# ----- the command line and the prompts -----------------------------------------------------------
h = subprocess.run([sys.executable, "-I", sys.argv[1], "--help"], capture_output=True, text=True)
check("--lead, --issue and --slug are on the command line",
      "--lead TEXT" in h.stdout and "--issue N" in h.stdout and "--slug SLUG" in h.stdout)
for extra in (["--pick", "a"], ["--resume"], ["--issue-less"], ["--topic", "x"], ["--answer", "s", "t"]):
    a = subprocess.run([sys.executable, "-I", sys.argv[1], "--repo", REPO, "--lead", "x", *extra],
                       capture_output=True, text=True)
    check(f"--lead is refused with {extra[0]}", a.returncode == 2 and "--lead works only the candidate it describes" in a.stderr)
for extra in (["--issue", "5"], ["--slug", "s"]):
    a = subprocess.run([sys.executable, "-I", sys.argv[1], "--repo", REPO, *extra], capture_output=True, text=True)
    check(f"{extra[0]} is refused without --lead", a.returncode == 2 and "--issue and --slug go with --lead" in a.stderr)
skill = Path(sys.argv[1]).resolve().parent.parent
A = (skill / "stages" / "A-investigate.md").read_text()
check("stage A is told how to treat the user's lead, in step 4 too, and where its search terms come from",
      "`candidate.lead` is true" in A and "(a lead: `needs-you` with the evidence instead" in A
      and "take them from its `why`" in A)
check("SKILL.md tells the launching session to use --lead for a known bug",
      '`--lead "TEXT"`' in (skill / "SKILL.md").read_text())

print("UNIT LEAD " + ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
