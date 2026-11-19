# Unit checks: --issue-less makes the scout a no-issue run. The prompt says so, and the driver drops
# any candidate that names an issue and works one at most, whatever the scout wrote.
# Usage: python3 -I unit_scout.py <contrib-run>.
import atexit, json, os, shutil, subprocess, sys, tempfile, importlib.machinery, importlib.util
from pathlib import Path
from types import SimpleNamespace
t = Path(tempfile.mkdtemp(prefix="contrib-unit-scout-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
ld = importlib.machinery.SourceFileLoader("cr", sys.argv[1])
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)

LEDGER = t / "ledger"
(LEDGER / "candidates").mkdir(parents=True)
(LEDGER / "rejects.md").write_text("# Rejected candidates\n\n")
CANDS = [
    {"slug": "has-issue", "title": "I", "source": "issue #5", "issue": 5, "why": "w"},
    {"slug": "issue-source", "title": "S", "source": "Issue #6", "issue": None, "why": "w"},
    {"slug": "mid-source", "title": "M", "source": "open issue #12116, unassigned", "issue": None, "why": "w"},
    {"slug": "hash-source", "title": "H", "source": "#77", "why": "w"},
    {"slug": "url-source", "title": "U", "source": "https://github.com/o/r/issues/5", "why": "w"},
    {"slug": "hash-issue", "title": "N", "source": "gap: n", "issue": "#123", "why": "w"},
    {"slug": "word-issue", "title": "W", "source": "gap: w", "issue": "issue 12", "why": "w"},
    {"slug": "see-source", "title": "E", "source": "gap: x (see #12116)", "issue": None, "why": "w"},
    {"slug": "repo-source", "title": "R", "source": "o/r#12116", "why": "w"},
    {"slug": "gh-source", "title": "G", "source": "GH-12116", "why": "w"},
    {"slug": "dash-source", "title": "D", "source": "issue-12116", "why": "w"},
    {"slug": "note-issue", "title": "O", "source": "gap: o", "issue": "12116 (open)", "why": "w"},
    {"slug": "list-issue", "title": "L", "source": "gap: l", "issue": [12116], "why": "w"},
    {"slug": "dict-issue", "title": "J", "source": "gap: j", "issue": {"number": 12116}, "why": "w"},
    {"slug": "known-slug", "title": "K", "source": "gap: k", "why": "w"},
    {"slug": "free-1", "title": "A", "source": "issue-less: gap in a", "issue": False, "why": "w"},
    {"slug": "free-2", "title": "B", "source": "small fix", "issue": "none", "why": "w"},
    {"slug": "free-3", "title": "C", "source": "Issueless small fix", "why": "w"},
]
ISSUE_SLUGS = ["has-issue", "issue-source", "mid-source", "hash-source", "url-source", "hash-issue", "word-issue",
               "see-source", "repo-source", "gh-source", "dash-source", "note-issue", "list-issue", "dict-issue"]

def run(issue_less):
    d = m.Driver.__new__(m.Driver)
    d.run_dir = t / f"run-{issue_less}"
    d.repo, d.repo_dir, d.upstream = "own/repo", t / "clone", "upstream/main"
    d.prof, d.prof_md, d.assign_first = {"CONTRIBUTOR": "me"}, "", True
    d.args = SimpleNamespace(topic="", scout_model="sonnet", issue_less=issue_less, limit=3)
    logs, prompts = [], []
    d.log = lambda msg, *a, **k: logs.append(msg)
    d.check_stop = lambda *a, **k: None
    d.snapshot = lambda dest: dest.mkdir(parents=True, exist_ok=True)
    d.all_states = lambda: [{"_dir": str(LEDGER / "candidates" / "known-slug")}]
    d.archive_transcripts = lambda home: None
    d.session_tmp = lambda home, make=True: t / "tmp"
    def session(role, sdir, prompt, *a, **k):
        prompts.append(prompt)
        (sdir / "candidates.json").write_text(json.dumps(CANDS))
        (sdir / "next.json").write_text(json.dumps({"action": "stage-done", "summary": "5 candidates"}))
        return {}
    d.session = session
    out = d.scout()
    return d, out, prompts, logs

d, out, prompts, logs = run(False)
check("without the flag every new slug is kept",
      [c["slug"] for c in out] == ISSUE_SLUGS + ["free-1", "free-2", "free-3"])
check("without the flag issue fields are left as written", out[0]["issue"] == 5 and out[len(ISSUE_SLUGS)]["issue"] is False)
check("without the flag the prompt does not limit sources", "issue-less fixes only" not in prompts[0])
check("without the flag nothing is logged", logs == [])
check("without the flag the run limit is --limit", d.run_limit() == 3)
check("without the flag the scout can run again", [c["slug"] for c in d.scout()][:1] == ["has-issue"]
      and len(prompts) == 2)

d, out, prompts, logs = run(True)
check("the prompt says the run takes issue-less fixes only", "takes issue-less fixes only" in prompts[0])
check("the prompt still asks for assign comments", "assign_comment" in prompts[0])
check("candidates naming an issue are dropped and one is kept", [c["slug"] for c in out] == ["free-1"])
check("the drop is logged with its count", any(f"dropped {len(ISSUE_SLUGS)} issue candidate" in l for l in logs))
check("issue-less wording and non-numbers are not taken for an issue", any("kept 1 of 3" in l for l in logs))
check("the kept candidate's issue field is cleared", out[0]["issue"] is None)
check("an issue-less run works one candidate", d.run_limit() == 1)
again = d.scout()
check("a second scout call returns nothing and starts no session", again == [] and len(prompts) == 1)
check("the second call is logged", any("not run again" in l for l in logs))

check("names_issue reads a bare issue number", m.names_issue({"issue": "12"}) and m.names_issue({"issue": 12}))
check("names_issue leaves gap sources alone", not any(m.names_issue({"source": s, "issue": None}) for s in
      ("gap: issues list is empty", "gap: &#39; in docs", "gap: C# 2 example", "gap: fails on Python 3.12")))
check("names_issue counts an unreadable issue field", m.names_issue({"issue": 0}) and m.names_issue({"issue": "n/a?"}))

d.repo = "own/repo"
d.args = SimpleNamespace(issue_less=True)
check("an issue-less run's resume command keeps the flag",
      d.resume_cmd() == "contrib-run --repo own/repo --resume --issue-less")
d.args = SimpleNamespace(issue_less=False)
check("a normal run's resume command is unchanged", d.resume_cmd() == "contrib-run --repo own/repo --resume")

stage = (Path(sys.argv[1]).resolve().parent.parent / "stages" / "scout.md").read_text()
check("scout.md says what the prompt's issue-less line means", "takes issue-less fixes only" in stage)
h = subprocess.run([sys.executable, "-I", sys.argv[1], "--help"], capture_output=True, text=True)
check("the flag is on the command line", "--issue-less" in h.stdout)
a = subprocess.run([sys.executable, "-I", sys.argv[1], "--repo", "own/repo", "--issue-less", "--answer", "s", "t"],
                   capture_output=True, text=True)
check("the flag is refused with --answer", a.returncode == 2 and "does nothing with --answer" in a.stderr)

print("UNIT SCOUT " + ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
