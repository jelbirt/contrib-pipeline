# Unit checks: the scout's probes. A probe is a test file the scout wrote, run by the driver on a
# fresh clone of the base with the profile's test command. The driver refuses a probe it cannot
# place safely, removes the whole clone after the run, keeps the file as it ran, and in an issue-less
# run keeps only a candidate whose probe failed on the base.
# Usage: python3 -I unit_probe.py <contrib-run>.
import atexit, json, os, shutil, sys, tempfile, importlib.machinery, importlib.util
from pathlib import Path
from types import SimpleNamespace
t = Path(tempfile.mkdtemp(prefix="contrib-unit-probe-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
ld = importlib.machinery.SourceFileLoader("cr", sys.argv[1])
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)

PROF = {"CONTRIBUTOR": "me", "TEST_CMD": "{env}/bin/python -m pytest -q {paths}", "TEST_FILES": "tests/*test_*.py core/*test_*.py",
        "SETUP_KEY": "uv.lock core", "TEST_EXIT_PASS": "0", "TEST_EXIT_FAIL": "1", "TEST_EXIT_NONE": "5"}

# ----- clear_tree: removing a folder a jailed command could write ---------------------------
victim = t / "victim"; (victim / "sub").mkdir(parents=True); (victim / "keep.txt").write_text("keep\n")
os.chmod(victim, 0o755); os.chmod(victim / "sub", 0o555)   # u+rwx would change it, so a chmod through a link shows
modes = lambda: (os.stat(victim).st_mode & 0o777, os.stat(victim / "sub").st_mode & 0o777)
tree = t / "tree"; (tree / "a" / "locked").mkdir(parents=True); (tree / "a" / "locked" / "f").write_text("x")
(tree / "shut").mkdir(); (tree / "shut" / "g").write_text("y")
os.symlink(victim, tree / "a" / "out"); os.symlink(victim / "keep.txt", tree / "a" / "keep.txt")
os.symlink(victim / "sub", tree / "a" / "subout")
os.chmod(tree / "a" / "locked", 0o500); os.chmod(tree / "shut", 0o000); os.chmod(tree / "a", 0o500); os.chmod(tree, 0o500)
check("clear_tree removes a tree with locked folders and links out of it", m.clear_tree(tree) and not os.path.lexists(tree))
check("clear_tree follows no link it finds, not even to change a mode",
      (victim / "keep.txt").read_text() == "keep\n" and modes() == (0o755, 0o555))
deep = t / "deep"; deep.mkdir()
fd = os.open(deep, os.O_RDONLY | os.O_DIRECTORY)
for _ in range(2100):         # deeper than rmtree's recursion and than a path name can be
    os.mkdir("a", dir_fd=fd)
    nfd = os.open("a", os.O_RDONLY | os.O_DIRECTORY, dir_fd=fd); os.close(fd); fd = nfd
os.symlink(victim, "out", dir_fd=fd)
os.close(fd)
check("clear_tree removes a tree too deep for rmtree or a path name", m.clear_tree(deep) and not os.path.lexists(deep)
      and (victim / "keep.txt").exists() and modes() == (0o755, 0o555))
os.symlink(victim, t / "linked")
check("clear_tree unlinks a symlink in a folder's place, not its target",
      m.clear_tree(t / "linked") and not os.path.lexists(t / "linked") and (victim / "keep.txt").exists()
      and modes() == (0o755, 0o555))

# req_cmd_test's scratch folder: its report/ is writable in the jail, so a run can leave it locked.
cd = m.Driver.__new__(m.Driver)
cd.cand = t / "cmdcand"; (cd.cand / "results").mkdir(parents=True)
cd.prof, cd.last_counts = {"TEST_CMD": "runner {paths}"}, None
cd.session_paths = lambda p: ["tests/test_x.py"]
cd.ensure_setup = lambda rid: 0
cd.cmd_values = lambda junit: {}
cd.cmd_jail = lambda argv, over=(), extra_rw=(): argv
ran = []
def cd_guarded(rid, argv, retries=None):
    ran.append(argv); rep = m.WORK / "tmp" / f"cmd-cmdcand-{rid}" / "report"
    (rep / "left.txt").write_text("x"); os.chmod(rep, 0o500)          # what a run could leave
    return 0, cd.cand / "results" / f"{rid}.log"
cd.guarded = cd_guarded
lt = m.WORK / "tmp" / "cmd-cmdcand-t1" / "report"; lt.mkdir(parents=True); os.chmod(lt, 0o500); os.chmod(lt.parent, 0o500)
rc, _, note = cd.req_cmd_test("t1", {"paths": ["tests/test_x.py"]})
check("a test run starts even when an earlier one left its scratch folder locked", rc == 0 and len(ran) == 1)
check("a test run removes its scratch folder even when the run locked it", not os.path.lexists(lt.parent))
real_clear = m.clear_tree; m.clear_tree = lambda p: not os.path.lexists(p)
lt.mkdir(parents=True)
rc, _, note = cd.req_cmd_test("t1", {"paths": ["tests/test_x.py"]})
m.clear_tree = real_clear
check("a scratch folder the driver cannot remove refuses the run", rc == 2 and note.startswith("refused:") and len(ran) == 1)
m.clear_tree(lt.parent)
check("clear_tree on nothing is done", m.clear_tree(t / "none"))

# ----- req_probe: where a probe may go, and what is left after it ---------------------------
home = t / "run" / "scout"
sdir = home / "session"
sdir.mkdir(parents=True); (home / "results").mkdir()
pc = t / "work" / "clones" / "_scout-probe"
d = m.Driver.__new__(m.Driver)
d.commands, d.prof, d.cand, d.probe_home, d.probe_clone, d.setup_base = True, dict(PROF), home, home, pc, "a" * 40
logs = []
d.log = lambda msg, *a, **k: logs.append(msg)
made = []
def mk(slug, branch, base, restore=True):
    if os.path.lexists(pc):
        raise AssertionError("make_clone found an old probe clone")
    made.append((branch, base, restore))
    (pc / "tests").mkdir(parents=True); (pc / "core").mkdir(); (pc / "tests" / "test_old.py").write_text("old\n")
    return pc
d.make_clone = mk
seen = []
def fake_test(rid, req):
    f = pc / req["paths"][0]
    seen.append((rid, req, f.read_bytes() if f.is_file() else None))
    if rid == "boom":
        raise RuntimeError("runner broke")
    if rid == "swap":
        # What a hostile probe could do in the jail: put a link to a host folder where its own
        # folder was, holding a file of its own name, and lock a folder it made.
        (victim / "test_probe_s.py").write_text("host file\n")
        shutil.rmtree(pc / "tests"); os.symlink(victim, pc / "tests")
        (pc / "core" / "deep").mkdir(); os.chmod(pc / "core", 0o500); os.chmod(pc, 0o500)
    if rid == "nofilt" and req.get("filter"):
        return 2, home / "results" / f"{rid}.log", "refused: this repo's profile has no TEST_FILTER_FLAG"
    if rid == "dirty":
        (pc / "tests" / "left_over.py").write_text("from the last probe\n")
    return 1, home / "results" / f"{rid}.log", "1 failed"
d.req_cmd_test = fake_test
TA = b"def test_a():\n    assert 1 == 2\n"
(sdir / "test_a.py").write_bytes(TA)
def probe(**req):
    return d.req_probe(req.get("id", "p"), req)

rc, _, note = probe(id="p1", source="test_a.py", path="tests/test_probe_a.py")
check("a probe runs the profile's test command on its new file", rc == 1 and seen[-1][0] == "p1"
      and seen[-1][1]["paths"] == ["tests/test_probe_a.py"] and seen[-1][2] == TA)
check("a probe expects fail unless it says otherwise", seen[-1][1]["expect"] == "fail")
check("a probe gets a fresh clone at the setup base, with nothing restored", made == [("contrib-probe", "a" * 40, False)])
check("the probe's clone is gone after the run", not os.path.lexists(pc))
check("the file as it ran is kept in results/", (home / "results" / "p1.probe").read_bytes() == TA)
probe(id="p2", source="test_a.py", path="tests/test_probe_b.py", expect="pass", filter="test_a")
check("expect and filter pass through", seen[-1][1]["expect"] == "pass" and seen[-1][1]["filter"] == "test_a")
check("each probe gets its own clone", len(made) == 2 and not os.path.lexists(pc))
probe(id="dirty", source="test_a.py", path="tests/test_probe_e.py")
probe(id="p4", source="test_a.py", path="tests/test_probe_f.py")
check("nothing a probe left reaches the next probe", not os.path.lexists(pc) and seen[-1][0] == "p4" and len(made) == 4)
try:
    probe(id="boom", source="test_a.py", path="tests/test_probe_c.py")
    raised = False
except RuntimeError:
    raised = True
check("the clone is removed even when the run fails", raised and not os.path.lexists(pc))
rc, _, note = probe(id="swap", source="test_a.py", path="tests/test_probe_s.py")
check("a probe that swaps its folder for a link to the host cannot make the driver delete there",
      (victim / "test_probe_s.py").read_text() == "host file\n" and (victim / "keep.txt").exists())
check("a probe that locks a folder still has its clone removed", not os.path.lexists(pc))
rc, _, note = probe(id="p1", source="test_a.py", path="tests/test_probe_g.py")
check("refused: an id that already ran", rc == 2 and "already ran" in note)
rc, _, note = probe(id="nofilt", source="test_a.py", path="tests/test_probe_j.py", filter="x")
rc2, _, note2 = probe(id="nofilt", source="test_a.py", path="tests/test_probe_j.py")
check("a probe the test command refused keeps its id free", rc == 2 and rc2 == 1 and seen[-1][0] == "nofilt"
      and (home / "results" / "nofilt.probe").exists() and not os.path.lexists(pc))
(pc / "tests" / "locked").mkdir(parents=True); os.chmod(pc / "tests", 0o500)
rc, _, note = probe(id="p5", source="test_a.py", path="tests/test_probe_h.py")
check("an old probe clone, even a locked one, is cleared before a probe", rc == 1 and seen[-1][0] == "p5"
      and not os.path.lexists(pc))
keep_clear, m.clear_tree = m.clear_tree, lambda p: False
n0 = len(seen)
rc, _, note = probe(id="p6", source="test_a.py", path="tests/test_probe_i.py")
check("refused: a clone the driver could not remove", rc == 2 and "could not remove" in note and len(seen) == n0)
m.clear_tree = keep_clear

n0, m0 = len(seen), len(made)
(sdir / "big_test.py").write_text("x" * (m.PROBE_MAX_BYTES + 1))
(t / "outside.py").write_text("secret\n")
os.symlink(t / "outside.py", sdir / "link_test.py")
(sdir / "dir_test.py").mkdir()
(sdir / "sub").mkdir(); (sdir / "sub" / "test_s.py").write_bytes(TA)
cases = [
    ("a source outside the session folder", dict(source="../../outside.py", path="tests/test_x.py"), "source must be"),
    ("an absolute source", dict(source=str(t / "outside.py"), path="tests/test_x.py"), "source must be"),
    ("a source in a subfolder", dict(source="sub/test_s.py", path="tests/test_x.py"), "source must be"),
    ("a source of ..", dict(source="..", path="tests/test_x.py"), "source must be"),
    ("a source that is not a string", dict(source=["test_a.py"], path="tests/test_x.py"), "source must be"),
    ("a symlinked source", dict(source="link_test.py", path="tests/test_x.py"), "not a file"),
    ("a source that is a folder", dict(source="dir_test.py", path="tests/test_x.py"), "not a file"),
    ("a missing source", dict(source="none.py", path="tests/test_x.py"), "not a file"),
    ("a source over the size limit", dict(source="big_test.py", path="tests/test_x.py"), "at most"),
    ("a path the test globs do not match", dict(source="test_a.py", path="src/x.py"), "test globs"),
    ("a path starting with a dash", dict(source="test_a.py", path="-tests/test_x.py"), "test globs"),
    ("a path under a SETUP_KEY path", dict(source="test_a.py", path="core/test_x.py"), "SETUP_KEY"),
    ("a path climbing out of the clone", dict(source="test_a.py", path="tests/../../test_x.py"), "plain file path"),
    ("a path the base already has", dict(source="test_a.py", path="tests/test_old.py"), "already has"),
    ("a path in a folder the base lacks", dict(source="test_a.py", path="tests/sub/test_x.py"), "does not exist"),
]
for i, (name, req, want) in enumerate(cases):
    rc, _, note = probe(id=f"r{i}", **req)
    check(f"refused: {name}", rc == 2 and note.startswith("refused:") and want in note)
check("no refused probe reached the test command", len(seen) == n0)
check("a probe refused before its clone makes none, and one refused after leaves none",
      len(made) == m0 + 3 and not os.path.lexists(pc))
check("refused probes keep no file in results/", not any((home / "results" / f"r{i}.probe").exists() for i in range(len(cases))))

d.probe_home = None
rc, _, note = probe(id="o1", source="test_a.py", path="tests/test_x.py")
check("a probe outside the scout is refused", rc == 2 and "scout request" in note)
d.probe_home, d.commands = home, False
rc, _, note = probe(id="o2", source="test_a.py", path="tests/test_x.py")
check("a probe in a repo with no test command is refused", rc == 2 and "scout request" in note)
d.commands = True
check("the driver logged no failure to remove a clone", not any("could not remove" in x for x in logs))

# ----- run_requests: a probe is judged as a test, expects fail, and is recorded -------------
r = m.Driver.__new__(m.Driver)
r.commands, r.prof, r.cand, r.guard_blocked = True, dict(PROF), home, False
r.check_stop = lambda *a, **k: None
r.log = lambda *a, **k: None
judged = []
def judge(kind, expect, rc, out, note):
    judged.append((kind, expect)); return rc == 1, note
r.judge_result = judge
def fake_probe(rid, req):
    r.last_counts = {"tests": 1, "failures": 1, "errors": 0, "skipped": 0}
    out = home / "results" / f"{rid}.log"; out.write_text("1 failed\n"); return 1, out, "1 failed"
r.req_probe = fake_probe
(home / "results" / "index.jsonl").unlink(missing_ok=True)
r.run_requests([{"kind": "probe", "id": "q1", "source": "test_a.py", "path": "tests/test_q.py"}])
rec = json.loads((home / "results" / "index.jsonl").read_text().splitlines()[-1])
check("a probe is judged as a test", judged == [("test", "fail")])
check("a probe's record says where it ran and how many failed", rec["kind"] == "probe" and rec["met"] is True
      and rec["probe"] == {"path": "tests/test_q.py", "source": "test_a.py"} and rec["counts"]["failures"] == 1)

# ----- scout(): probes in the loop, and the driver-side check -------------------------------
LEDGER = t / "ledger"
(LEDGER / "candidates").mkdir(parents=True); (LEDGER / "rejects.md").write_text("# Rejected candidates\n\n")
TEST_A = "def test_a():\n    assert broken() == 1\n"
CANDS = [{"slug": "free-a", "title": "A", "source": "gap: a", "why": "w", "probe": "p-fail"},
         {"slug": "free-b", "title": "B", "source": "gap: b", "why": "w", "probe": "p-pass"},
         {"slug": "free-c", "title": "C", "source": "gap: c", "why": "w"},
         {"slug": "free-d", "title": "D", "source": "gap: d", "why": "w", "probe": "p-other"},
         {"slug": "free-e", "title": "E", "source": "gap: e", "why": "w", "probe": "p odd"},
         {"slug": "free-f", "title": "F", "source": "gap: f", "why": "w", "probe": "p-ref"}]

def scout(issue_less, **prof):
    d = m.Driver.__new__(m.Driver)
    d.run_dir = t / f"srun-{issue_less}-{len(prof)}"
    d.repo, d.repo_dir, d.upstream = "own/repo", t / "clone", "upstream/main"
    d.prof, d.prof_md, d.assign_first = {"CONTRIBUTOR": "me", **prof}, "", False
    d.commands = bool(d.prof.get("TEST_CMD", "").strip())
    d.args = SimpleNamespace(topic="", scout_model="sonnet", issue_less=issue_less, limit=3)
    logs, prompts, systems, ran, during = [], [], [], [], []
    d.log = lambda msg, *a, **k: logs.append(msg)
    d.check_stop = lambda *a, **k: None
    d.snapshot = lambda dest: dest.mkdir(parents=True, exist_ok=True)
    d.all_states = lambda: []
    d.archive_transcripts = lambda home: None
    d.session_tmp = lambda home, make=True: t / "tmp"
    d.git = lambda *a, **k: "b" * 40
    dropped = []
    d.drop_copy = lambda snap: dropped.append(snap)
    d.cut_note = ""
    def run_requests(reqs, driver=False):
        ran.append([q.get("kind") for q in reqs])
        during.append(tuple(getattr(d, a, None) for a in ("probe_home", "probe_clone", "setup_base")))
        res = d.cand / "results"
        if getattr(d, "probe_clone", None):
            d.probe_clone.mkdir(parents=True, exist_ok=True)      # as a first probe would make it
        (res / "p-fail.probe").write_text(TEST_A); (res / "p_odd.probe").write_text(TEST_A)
        with open(res / "index.jsonl", "a") as f:
            for rid, kind, exp, met, note in (("p-fail", "probe", "fail", True, "1 failed"),
                                              ("p-pass", "probe", "fail", False, "1 passed"),
                                              ("p-other", "test", "fail", True, "1 failed"),
                                              ("p_odd", "probe", "fail", True, "1 failed"),
                                              ("p-ref", "probe", "fail", True, "refused: an odd judge")):
                f.write(json.dumps({"id": rid, "kind": kind, "expect": exp, "met": met, "note": note,
                                    "log": f"results/{rid}.log",
                                    "probe": {"path": "tests/test_p.py", "source": "probes/p.py"}}) + "\n")
    d.run_requests = run_requests
    turn = [0]
    def session(role, sd, prompt, system, *a, **k):
        prompts.append(prompt); systems.append(system); turn[0] += 1
        if turn[0] == 1:
            (sd / "next.json").write_text(json.dumps({"action": "run", "requests": [
                {"kind": "gh", "id": "g", "args": "issue view 1"},
                {"kind": "probe", "id": "p-fail", "source": "probes/p.py", "path": "tests/test_p.py"},
                {"kind": "check", "id": "c", "name": "LINT"}]}))
        else:
            (sd / "candidates.json").write_text(json.dumps(CANDS))
            (sd / "next.json").write_text(json.dumps({"action": "stage-done", "summary": "4 candidates"}))
        return {}
    d.session = session
    out = d.scout()
    return d, out, prompts, systems, logs, ran, during, dropped

d, out, prompts, systems, logs, ran, during, dropped = scout(True, **PROF)
check("the scout is told about probes", "## Probes" in systems[0] and PROF["TEST_CMD"] in systems[0]
      and "`tests/*test_*.py`" in systems[0])
check("the issue-less prompt says a candidate needs a failing probe", "only with a probe that failed" in prompts[0])
check("the scout may ask for gh reads and probes, nothing else", ran == [["gh", "probe"]]
      and "1 of your requests were not gh reads and probes" in prompts[1])
check("probes run with the scout's folder, a throwaway clone and the base",
      during == [(d.run_dir / "scout", m.WORK / "clones" / "_scout-probe", "b" * 40)])
check("an issue-less run keeps only a candidate whose probe failed, one at most", [c["slug"] for c in out] == ["free-a"]
      and "scout: kept 1 of 2 issue-less candidates; at most one per run" in logs)
check("the kept candidate carries the probe as it ran", out[0]["probe"]["id"] == "p-fail"
      and out[0]["probe"]["test"] == TEST_A and out[0]["probe"]["path"] == "tests/test_p.py"
      and out[0]["probe"]["log"].endswith("scout/results/p-fail.log"))
check("the drop is logged", "scout: dropped 4 issue-less candidate(s) with no probe that failed on the base" in logs)
check("after the scout no probe state is left", d.probe_home is None and d.probe_clone is None and d.setup_base is None
      and not (m.WORK / "clones" / "_scout-probe").exists() and dropped == [m.WORK / "snap" / "scout.build"])
check("probes do not make a later stage's request look like the scout's", d.clone == m.Driver.clone.__get__(d))

d, out, prompts, systems, logs, ran, during, dropped = scout(False, **PROF)
check("without --issue-less a candidate needs no probe", [c["slug"] for c in out] == ["free-a", "free-b", "free-c", "free-d", "free-e", "free-f"])
check("without --issue-less a failing probe is still attached", out[0]["probe"]["id"] == "p-fail"
      and "probe" not in out[1] and "probe" not in out[2] and "probe" not in out[3]
      and out[4]["probe"]["id"] == "p_odd" and "probe" not in out[5])
check("a candidate's probe id is read as the driver named it, and a refused record proves nothing",
      out[4]["probe"]["id"] == "p_odd" and out[4]["probe"]["test"] == TEST_A and "probe" not in out[5])

d, out, prompts, systems, logs, ran, during, dropped = scout(True)
check("a repo with no test command gets no probes", "## Probes" not in systems[0] and ran == [["gh"]]
      and "only with a probe" not in prompts[0] and "not gh reads and did not run" in prompts[1])
check("with no test command, an issue-less candidate is not held to a probe", [c["slug"] for c in out] == ["free-a"])
check("with no test command no probe state is set", during == [(None, None, None)])

print("UNIT PROBE PASS" if ok else "UNIT PROBE FAIL")
sys.exit(0 if ok else 1)
