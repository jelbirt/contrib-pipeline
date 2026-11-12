# Unit checks for commands mode (SPEC phase 2): profile keys, command rendering, test judging,
# request kinds and paths, assignment first, the shallow clone, retest, session settings and the
# sweep. Each guard also has a mutant: the driver's source with only that guard taken out, which
# the guard's check must fail; that shows the check tests the guard and not something else.
import atexit, json, os, shutil, subprocess, sys, tempfile, types
from pathlib import Path
from types import SimpleNamespace
t = Path(tempfile.mkdtemp(prefix="contrib-unit-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
DRV = os.path.realpath(sys.argv[1])
SRC = Path(DRV).read_text()


def load(src):
    """The driver as a module, from src, with the real file's path (so SKILL finds its folders)."""
    mod = types.ModuleType("cr")
    mod.__file__ = DRV
    exec(compile(src, DRV, "exec"), mod.__dict__)
    return mod


m = load(SRC)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


SRCREPO = t / "src"
git("init", "-q", "-b", "main", str(SRCREPO))
for i in (1, 2):
    (SRCREPO / "f.txt").write_text(f"{i}\n")
    git("add", "f.txt", cwd=SRCREPO)
    git("-c", "user.name=u", "-c", "user.email=u@l", "commit", "-qm", f"c{i}", cwd=SRCREPO)
SHALLOW = t / "shallow"
git("clone", "-q", "--depth", "1", f"file://{SRCREPO}", str(SHALLOW))
CMD = dict(REPO_DIR=str(SRCREPO), UPSTREAM_REMOTE="upstream", BASE_BRANCH="main", CONTRIBUTOR="me",
           GUARD="/bin/true", SETUP_CMD="setup {env}", SETUP_KEY="lock", TEST_CMD="runner --junit={junit} {paths}",
           TEST_EXIT_PASS="0", TEST_EXIT_FAIL="1", TEST_EXIT_NONE="5", CHECKS="FORMAT", CHECK_FORMAT="fmt {paths}",
           GATE_CHECKS="FORMAT", ASSIGN_FIRST="1")
C = dict(tests=0, failures=0, errors=0, skipped=0)


def without(d, *keys):
    return {k: v for k, v in d.items() if k not in keys}


def mk(m, **over):
    d = m.Driver.__new__(m.Driver)
    d.prof = {**CMD, **over}
    d.repo, d.repo_dir = "x-org/y", Path(d.prof["REPO_DIR"])
    d.commands = bool(d.prof.get("TEST_CMD", "").strip())
    d.assign_first = d.prof.get("ASSIGN_FIRST", "") == "1"
    d.args = SimpleNamespace(stub=True, real_requests=False)
    d.last_counts, d.env_dir, d.guard_blocked, d.cut_note = None, None, False, ""
    d.cand = Path(os.environ["CONTRIB_LEDGER"]) / "candidates" / "c1"
    (d.cand / "results").mkdir(parents=True, exist_ok=True)
    (d.cand / "session").mkdir(parents=True, exist_ok=True)
    d.log = lambda *a, **k: None
    d.check_stop = lambda *a, **k: None
    return d


def raises(fn, text):
    try:
        fn()
    except (RuntimeError, SystemExit) as e:
        return text in str(e)
    return False


# ----- checks: each takes a module and returns True when its guard holds -----------------------
def c_missing_key(m):
    return ("TEST_EXIT_FAIL is missing or empty" in m.profile_problems(without(CMD, "TEST_EXIT_FAIL"))
            and "REPO_DIR is missing or empty" in m.profile_problems(without(CMD, "REPO_DIR"), base_only=True)
            and "CHECK_FORMAT is missing or empty" in m.profile_problems(without(CMD, "CHECK_FORMAT"))
            and m.profile_problems(CMD) == [])
def c_paths_word(m):
    return any("no {paths}" in p for p in m.profile_problems({**CMD, "TEST_CMD": "runner --junit={junit}"}))
def c_unknown_slot(m):
    return any("unknown slot {home}" in p for p in m.profile_problems({**CMD, "SETUP_CMD": "setup {home}"}))
def c_gate_checks(m):
    return any("GATE_CHECKS names LINT" in p for p in m.profile_problems({**CMD, "GATE_CHECKS": "LINT"}))
def c_render_list(m):
    return m.render_cmd("run {paths}", {}, {"paths": ["a b", "x;rm -rf ~"]}) == ["run", "a b", "x;rm -rf ~"]
def c_render_unknown(m):
    return raises(lambda: m.render_cmd("run {nope}", {}), "has no value")
def c_judge_none(m):
    return m.judge_test(5, dict(C), "fail", CMD)[1].startswith("no test ran")
def c_judge_other_rc(m):
    return "neither the pass nor the fail code" in m.judge_test(2, None, "fail", CMD, report=False)[1]
def c_judge_fail_needs_failure(m):
    return m.judge_test(1, dict(C, tests=1, errors=1), "fail", CMD)[0] is False
def c_judge_pass_needs_tests(m):
    return m.judge_test(0, dict(C, tests=2, skipped=2), "pass", CMD)[0] is False
def c_judge_report_missing(m):
    return m.judge_test(0, None, "pass", CMD)[0] is False
def c_result_commands_pass(m):
    d = mk(m)
    out = d.cand / "results" / "p.log"; out.write_text("....\n4 passed\n")
    d.last_counts = dict(C, tests=4)
    return d.judge_result("test", "pass", 0, out, "")[0] is True
def c_result_unknown_kind(m):
    d = mk(m)
    return d.judge_result("fmt", "fail", 2, d.cand / "results" / "none.log",
                          "unknown request kind 'fmt': this repo's kinds are test, check and gh")[0] is False
def c_dispatch(m):
    d = mk(m)
    d.run_requests([{"id": "r1", "kind": "clippy", "crates": ["x"], "expect": "any"}])
    rec = json.loads((d.cand / "results" / "index.jsonl").read_text().splitlines()[-1])
    return rec["id"] == "r1" and rec["exit"] == 2 and rec["met"] is False and "unknown request kind" in rec["note"]
def c_paths_dash(m):
    d = mk(m)
    c = t / "clone-paths"; c.mkdir(exist_ok=True)
    (c / "-x").write_text(""); (c / "ok.py").write_text("")
    d.clone = lambda: c
    return d.session_paths(["-x"]) is None and d.session_paths(["ok.py"]) == ["ok.py"]
def assign(m, who):
    d = mk(m)
    calls = []
    d.issue_assignees = lambda n: who
    d.finish = lambda status, **i: calls.append(status) or status
    d.reject = lambda *a: calls.append("rejected")
    return d.assignment_stop(5, {"assign_comment": "Could I take this?"}), calls, d
def c_assign_other(m):
    r, calls, d = assign(m, ["someone"])
    return r == "abandoned" and "rejected" in calls
def c_assign_none(m):
    r, calls, d = assign(m, [])
    return r == "needs-you" and (d.cand / "session" / "assign-comment.md").read_text().startswith("Could I take this?")
def c_assign_me(m):
    r, calls, d = assign(m, ["Me"])
    return r == "" and calls == []
def c_recheck(m):
    d = mk(m)
    d.st = lambda: {"issue": 5}
    d.finish = lambda status, **i: status
    d.is_assigned = lambda n: False
    lost = d.assignment_recheck()
    d.is_assigned = lambda n: True
    return lost == "needs-you" and d.assignment_recheck() == ""
def c_answer(m):
    d = mk(m)
    (d.cand / "state.json").write_text(json.dumps({"status": "needs-you", "issue": 5, "repo": "x-org/y"}))
    d.is_assigned = lambda n: False
    return raises(lambda: d.answer_setup("c1", "go"), "is not assigned to @me")
def c_shallow(m):
    d = mk(m, REPO_DIR=str(SHALLOW))
    full = mk(m)
    try:
        full.refuse_shallow()
    except RuntimeError:
        return False
    return raises(d.refuse_shallow, "is a shallow clone")
def c_retest(m):
    return raises(lambda: mk(m).retest("abc", False), "cargo profiles only")
def settings(m, **over):
    return json.dumps(mk(m, **over).settings_for([t / "w"], t / "clone"))
def c_session_deny(m):
    return '"Bash(pytest:*)"' in settings(m, SESSION_DENY="pytest")
def c_ref_host(m):
    return "raw.githubusercontent.com" not in settings(m) and "example.org" in settings(m, REF_HOST="example.org")
def c_sweep(m):
    d = mk(m, JAIL_PROCS="python3")
    root = t / "sweep-root"; root.mkdir(exist_ok=True)
    p = subprocess.Popen(["python3", "-c", "import time; time.sleep(60)", str(root / "x")])
    try:
        import time; time.sleep(0.3)
        d.sweep([root])
        try:
            return p.wait(timeout=5) == -9
        except subprocess.TimeoutExpired:
            return False
    finally:
        if p.poll() is None:
            p.kill(); p.wait()
def c_init_refusal(m, src=None):
    pdir = t / "profiles"; pdir.mkdir(exist_ok=True)
    (pdir / "x-org-y.env").write_text("".join(f"{k}={v}\n" for k, v in without(CMD, "TEST_EXIT_FAIL").items()))
    (pdir / "x-org-y.md").write_text("# hand profile\n")
    f = t / "drv-init.py"; f.write_text(src or SRC)
    r = subprocess.run([sys.executable, "-c", f"exec(compile(open({str(f)!r}).read(), {DRV!r}, 'exec'), "
                        f"{{'__name__': '__main__', '__file__': {DRV!r}}})", "--repo", "x-org/y", "--limit", "1"],
                       capture_output=True, text=True, env=dict(os.environ, CONTRIB_PROFILE_DIR=str(pdir)), timeout=60)
    return r.returncode == 2 and "is not usable" in r.stderr and "TEST_EXIT_FAIL" in r.stderr


def setup_driver(m, base):
    """A driver whose ensure_setup and cmd_jail only build their bwrap argv, captured, not run."""
    shutil.rmtree(m.WORK / "envs", ignore_errors=True)
    d = mk(m, SETUP_KEY="f.txt")
    d.st = lambda: {"base_sha": base}
    d.cap, d.target_name = [], None
    d.guarded = lambda rid, argv, retries=0: (d.cap.append(argv), (0, ""))[1]
    d.clone = lambda: SRCREPO
    d.git_dir_check = lambda keep=None: SRCREPO / ".git"
    return d


C1, C2 = git("rev-parse", "HEAD~1", cwd=SRCREPO), git("rev-parse", "HEAD", cwd=SRCREPO)


def bind_kind(argv, path):
    """The bwrap option that binds path at itself: --bind, --ro-bind, or None."""
    for i in range(len(argv) - 2):
        if argv[i] in ("--bind", "--ro-bind") and argv[i + 1] == argv[i + 2] == str(path):
            return argv[i]
    return None


def c_cmd_no_net(m):
    d = setup_driver(m, C2)
    if d.ensure_setup("r1") != 0 or len(d.cap) != 1:
        return False
    run = d.cmd_jail(["runner"])
    return "--unshare-net" not in d.cap[0] and "--unshare-net" in run


def c_env_readonly(m):
    d = setup_driver(m, C2)
    d.ensure_setup("r1")
    return bind_kind(d.cap[0], d.env_dir) == "--bind" and bind_kind(d.cmd_jail(["runner"]), d.env_dir) == "--ro-bind"


def c_setup_key(m):
    d1, d2, d3 = setup_driver(m, C1), setup_driver(m, C2), setup_driver(m, C2)
    for d in (d1, d2, d3):
        d.ensure_setup("r1")
    return d1.env_dir != d2.env_dir and d2.env_dir == d3.env_dir and len(d3.cap) == 0


def c_requests_text(m):
    d = mk(m)
    d.prof_md = "# hand profile\n"
    text = d.system_text("B-fix.md")
    return "## Runs you can request" in text and "`fmt {paths}`" in text and "`runner --junit={junit} {paths}`" in text


# ----- the review's fixes -----------------------------------------------------------------------
def c_paths_at(m):
    d = mk(m)
    c = t / "clone-at"; c.mkdir(exist_ok=True)
    (c / "@args").write_text(""); (c / "ok.py").write_text("")
    d.clone = lambda: c
    return d.session_paths(["ok.py", "@args"]) is None and d.session_paths(["ok.py"]) == ["ok.py"]


def c_filter_at(m):
    d = mk(m, TEST_FILTER_FLAG="-k")
    c = t / "clone-at"; c.mkdir(exist_ok=True); (c / "ok.py").write_text("")
    d.clone = lambda: c
    rc, _, note = d.req_cmd_test("r1", {"paths": ["ok.py"], "filter": "@args"})
    return rc == 2 and note.startswith("refused: the filter")


def c_without_list(m):
    d = mk(m)
    d.clone = lambda: SRCREPO
    rc, _, note = d.req_cmd_test("r1", {"paths": ["f.txt"], "without": "f.txt"})
    return rc == 2 and note == "refused: without must be a list of paths"


def c_without_list_cargo(m):
    d = mk(m)
    d.commands, d.clone = False, (lambda: SRCREPO)
    rc, _, note = d.req_test("r1", {"crate": "xerj-api", "target": "lib", "without": "f.txt"})
    return rc == 2 and note == "without must be a list of paths"


def c_driver_error(m):
    d = mk(m)
    out = d.cand / "results" / "e.log"; out.write_text("guard: started\n")
    d.last_counts = dict(C, tests=1, failures=1)      # a stale report from an earlier run
    return all(d.judge_result("test", "fail", 1, out, note)[0] is False
               for note in ("driver error: boom", "the dependency setup failed"))


def c_report_word(m):
    d = mk(m)          # TEST_CMD writes its report as --junit={junit}: one word holding the slot
    out = d.cand / "results" / "w.log"; out.write_text("guard: started\n")
    d.last_counts = None
    return d.judge_result("test", "pass", 0, out, "")[0] is False


def c_skipped_not_gone(m):
    skipped = m.judge_test(0, dict(C, tests=2, skipped=2), "pass", CMD)
    none = m.judge_test(5, None, "pass", CMD, report=False)
    return skipped[0] is False and not m.gone_note(skipped[1]) and m.gone_note(none[1])


def c_gate_missing(m):
    d = mk(m)
    c = t / "clone-gate"; c.mkdir(exist_ok=True); (c / "kept.py").write_text("")
    d.clone = lambda: c
    run, gone = d.replay_split([{"paths": ["kept.py"]}, {"paths": ["kept.py", "renamed.py"]}], "gate-x")
    return [r["id"] for r in run] == ["gate-x-t0"] and [r["id"] for r in gone] == ["gate-x-t1"]


RENAME = t / "rename"
git("init", "-q", "-b", "main", str(RENAME))
(RENAME / "tests").mkdir()
(RENAME / "tests" / "test_a.py").write_text("".join(f"def test_{i}():\n    pass\n" for i in range(20)))
(RENAME / "setup.lock").write_text("v1\n")
git("add", "-A", cwd=RENAME); git("-c", "user.name=u", "-c", "user.email=u@l", "commit", "-qm", "base", cwd=RENAME)
RBASE = git("rev-parse", "HEAD", cwd=RENAME)
git("mv", "tests/test_a.py", "tests/test_b.py", cwd=RENAME)
with open(RENAME / "tests" / "test_b.py", "a") as f:
    f.write("def test_new():\n    pass\n")
(RENAME / "setup.lock").write_text("v2\n")
git("add", "-A", cwd=RENAME); git("-c", "user.name=u", "-c", "user.email=u@l", "commit", "-qm", "fix", cwd=RENAME)


def rename_driver(m, **over):
    d = mk(m, TEST_FILES="tests/test_*.py", SETUP_KEY="setup.lock", **over)
    d.clone = lambda: RENAME
    d.cgit = lambda *a, check=True, index=False: git(*a, cwd=RENAME)
    return d


def c_renamed_tests(m):
    return rename_driver(m).changed_test_files(RBASE) == ["tests/test_b.py"]


def c_setup_touched(m):
    return rename_driver(m).setup_paths_touched(RBASE) == ["setup.lock"]


def c_issue_forms(m):
    f = m.issue_number
    return (f("#12"), f("12"), f(12), f(None), f(""), f(True), f(1.0), f("12 or 13"), f(0)) == \
        (12, 12, 12, None, None, -1, -1, -1, -1)


def c_issue_refused(m):
    d = mk(m)
    calls = []
    d.git = lambda *a, **k: "0" * 40
    d.upstream, d.run_id, d.prof["BRANCH_PREFIX"] = "upstream/main", "r", "fix/"
    d.reject = lambda *a: calls.append("rejected")
    d.finish = lambda status, **i: calls.append(status) or status
    d.issue_assignees = lambda n: []
    return d.work_candidate({"slug": "bad-issue", "title": "t", "issue": "see the thread"}) == "abandoned" \
        and calls == ["rejected", "abandoned"]


def c_tools_key(m):
    a, b = t / "tools-a", t / "tools-b"
    a.mkdir(exist_ok=True); b.mkdir(exist_ok=True)
    d1, d2 = setup_driver(m, C2), setup_driver(m, C2)
    d1.prof["TOOLS"], d2.prof["TOOLS"] = str(a), str(b)
    d1.ensure_setup("r1"); d2.ensure_setup("r1")
    return d1.env_dir != d2.env_dir


def c_unready_cleanup(m):
    d = setup_driver(m, C2)
    root = d.env_root()
    for n in ("half-done", "cache"):
        (root / n).mkdir(parents=True, exist_ok=True)
    d.ensure_setup("r1")
    return not (root / "half-done").exists() and (root / "cache").is_dir() and d.env_dir.is_dir()


def safe(fn, mod, *a):
    try:
        return bool(fn(mod, *a))
    except Exception as e:
        print(f"     ({fn.__name__}: {type(e).__name__}: {str(e)[:200]})")
        return False


CHECKS = [c_missing_key, c_paths_word, c_unknown_slot, c_gate_checks, c_render_list, c_render_unknown,
          c_judge_none, c_judge_other_rc, c_judge_fail_needs_failure, c_judge_pass_needs_tests,
          c_judge_report_missing, c_result_commands_pass, c_result_unknown_kind, c_dispatch, c_paths_dash,
          c_assign_other, c_assign_none, c_assign_me, c_recheck, c_answer, c_shallow, c_retest,
          c_session_deny, c_ref_host, c_sweep, c_init_refusal, c_cmd_no_net, c_env_readonly, c_setup_key,
          c_requests_text, c_paths_at, c_filter_at, c_without_list, c_without_list_cargo, c_driver_error,
          c_report_word, c_skipped_not_gone, c_gate_missing, c_renamed_tests, c_setup_touched, c_issue_forms,
          c_issue_refused, c_tools_key, c_unready_cleanup]
for fn in CHECKS:
    check(fn.__name__[2:], safe(fn, m))
for name in ("pydantic-pydantic", "xerj-org-xerj"):
    check(f"the real {name} profile has no problems",
          m.profile_problems(m.load_env(m.SKILL / "profiles" / f"{name}.env")) == [])
# The xerj lines moved out of the shared prompts live in xerj's hand profile instead.
shared = "\n".join((m.SKILL / p).read_text() for p in ("rules/common.md", "stages/A-investigate.md",
                   "stages/B-fix.md", "stages/C-finish.md", "stages/scout.md"))
for word in ("xerj", "cargo", "clippy", "catch-lenient", "8.13.4", "engine/crates"):
    check(f"the shared prompts do not name {word}", word not in shared.lower())
xmd = (m.SKILL / "profiles" / "xerj-org-xerj.md").read_text()
for word in ("xerj hub feedback", "catch-lenient", "8.13.4", "engine/crates/", "node-start", "clippy", "CHANGELOG"):
    check(f"xerj's profile holds {word}", word in xmd)

# ----- mutants: (check, the guard's code, the same code without the guard) -----------------------
MUTANTS = [
    (c_missing_key, 'out = [f"{k} is missing or empty" for k in dict.fromkeys(need) if not prof.get(k, "").strip()]', "out = []"),
    (c_paths_word, 'if "{paths}" not in shlex.split(prof.get("TEST_CMD", "")):', "if False:"),
    (c_unknown_slot, 'bad = set(re.findall(r"\\{(\\w+)\\}", w)) - CMD_SLOTS', "bad = set()"),
    (c_gate_checks, "        if n not in checks:\n", "        if False:\n"),
    (c_render_list, "argv += [str(x) for x in lists[m.group(1)]]", 'argv += " ".join(map(str, lists[m.group(1)])).split()'),
    (c_render_unknown, 'raise RuntimeError(f"command slot {{{x.group(1)}}} has no value here")', "return x.group(0)"),
    (c_judge_none, "if none_rc is not None and rc == none_rc:", "if False:"),
    (c_judge_other_rc, "if rc not in (ok_rc, fail_rc):", "if False:"),
    (c_judge_fail_needs_failure, 'if counts is not None and (counts["failures"] == 0 or counts["errors"] > 0):', "if False:"),
    (c_judge_pass_needs_tests, 'if counts is not None and counts["tests"] - counts["skipped"] <= 0:', "if False:"),
    (c_judge_report_missing, "if report and counts is None:", "if False:"),
    (c_result_commands_pass, "        if self.commands:\n            if log.startswith(\"[stub]\"):",
     "        if False:\n            if log.startswith(\"[stub]\"):"),
    (c_result_unknown_kind, 'note.startswith(("refused:", "unknown request kind", "driver error",',
     'note.startswith(("refused:", "driver error",'),
    (c_dispatch, 'if self.commands and kind not in ("test", "check", "gh"):', "if False:"),
    (c_paths_dash, 'if f is None or p.startswith(("-", "@")) or any(c in p for c in "\\n\\r"):', "if f is None:"),
    (c_assign_other, "        if who:\n            why = f\"issue #{n} is assigned to", "        if False:\n            why = f\"issue #{n} is assigned to"),
    (c_assign_none, "        if any(w.lower() == me.lower() for w in who):\n            return \"\"", "        if True:\n            return \"\""),
    (c_assign_me, "        if any(w.lower() == me.lower() for w in who):\n            return \"\"", "        if False:\n            return \"\""),
    (c_recheck, "        n = self.st().get(\"issue\")\n        if self.assign_first and isinstance(n, int) and not self.is_assigned(n):",
     "        n = self.st().get(\"issue\")\n        if False:"),
    (c_answer, 'if self.assign_first and isinstance(st.get("issue"), int) and not self.is_assigned(st["issue"]):', "if False:"),
    (c_shallow, 'if self.git("rev-parse", "--is-shallow-repository", check=False) == "true":', "if False:"),
    (c_retest, "        if self.commands:\n            raise RuntimeError(\"retest runs cargo", "        if False:\n            raise RuntimeError(\"retest runs cargo"),
    (c_session_deny, '+ [f"Bash({w}:*)" for w in self.prof.get("SESSION_DENY", "").split()]', "+ []"),
    (c_ref_host, 'domains = [] if only is not None else self.prof.get("REF_HOST", "").split()',
     'domains = [] if only is not None else ["raw.githubusercontent.com"]'),
    (c_sweep, ' and comm not in self.prof.get("JAIL_PROCS", "").split():', ":"),
    (c_init_refusal, "        if probs:\n            print(f\"profile", "        if False:\n            print(f\"profile"),
    (c_cmd_no_net, "        return self.jail('exec \"$@\"', rw=(self.clone(), *extra_rw),",
     "        return self.jail('exec \"$@\"', net=True, rw=(self.clone(), *extra_rw),"),
    (c_env_readonly, "rw=(self.clone(), *extra_rw), ro=(self.env_dir, *self.tool_dirs()),",
     "rw=(self.clone(), self.env_dir, *extra_rw), ro=(*self.tool_dirs(),),"),
    (c_setup_key, 'self.prof.get("TOOLS", ""), *ids]).encode()', 'self.prof.get("TOOLS", "")]).encode()'),
    (c_requests_text, "*([self.requests_text()] if self.commands else []), packet,", "packet,"),
    (c_paths_at, 'p.startswith(("-", "@"))', 'p.startswith("-")'),
    (c_filter_at, 'filt.startswith(("-", "@"))', 'filt.startswith("-")'),
    (c_without_list, '        if not isinstance(without, list):\n            return 2, out, "refused: without',
     '        if False:\n            return 2, out, "refused: without'),
    (c_without_list_cargo, '        if not isinstance(without, list):\n            return 2, out, "without must',
     '        if False:\n            return 2, out, "without must'),
    (c_driver_error, '"unknown request kind", "driver error",\n                                              "the dependency setup failed"))',
     '"unknown request kind"))'),
    (c_report_word, 'return any("{junit}" in w for w in shlex.split(prof.get("TEST_CMD", "")))',
     'return "{junit}" in shlex.split(prof.get("TEST_CMD", ""))'),
    (c_skipped_not_gone, '"every test it found was skipped, so nothing passed"', '"no test ran (none collected, or all skipped)"'),
    (c_gate_missing, "(run if all(os.path.lexists(self.clone() / p) for p in t.get(\"paths\", [])) else gone)",
     "(run if True else gone)"),
    (c_renamed_tests, '"--name-only", "--no-renames", "--diff-filter=AM"', '"--name-only", "--diff-filter=AM"'),
    (c_setup_touched, "        if not keys:\n            return []\n        return [n for n",
     "        if True:\n            return []\n        return [n for n"),
    (c_issue_forms, "    if isinstance(x, bool):\n        return -1\n", ""),
    (c_issue_refused, "        if self.assign_first and n == -1:", "        if False:"),
    (c_tools_key, 'self.prof.get("JAIL_ENV", ""),\n                                        self.prof.get("TOOLS", ""),',
     'self.prof.get("JAIL_ENV", ""),'),
    (c_unready_cleanup, 'if d.is_dir() and d.name not in ("cache", "cargo") and d != self.env_dir and not',
     'if False and d.name not in ("cache", "cargo") and d != self.env_dir and not'),
]
for fn, old, new in MUTANTS:
    n = SRC.count(old)
    if n != 1:
        check(f"mutant for {fn.__name__[2:]}: its guard's code is found once (found {n})", False)
        continue
    msrc = SRC.replace(old, new)
    if fn is c_init_refusal:
        res = safe(fn, m, msrc)
    else:
        try:
            mm = load(msrc)
        except Exception as e:
            check(f"mutant for {fn.__name__[2:]} loads ({type(e).__name__}: {e})", False)
            continue
        res = safe(fn, mm)
    check(f"without its guard, {fn.__name__[2:]} fails", not res)
untested = {f.__name__ for f in CHECKS} - {f.__name__ for f, _, _ in MUTANTS}
check(f"every check has a mutant (missing: {sorted(untested)})", not untested)
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
