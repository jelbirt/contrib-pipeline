# Unit checks for contrib-check (SPEC phase 3): its verdicts on small fake repos, offline (gh is a
# stub that reports no open PRs), for a xerj-style profile (crates, a ratchet file, CHANGELOG) and a
# pydantic-style one (areas, SETUP_KEY), plus --where and the profile checks. The xerj cases were
# first run against contrib-check as it was before its lists moved into the profile, and gave the
# same verdicts. Each new guard has a mutant: the script with only that guard taken out, which its
# check must fail.
# Run as the other unit files are: python3 -I unit_check.py <path to contrib-run>; contrib-check is
# found next to it. CONTRIB_CHECK overrides that path.
import atexit, json, os, shlex, shutil, subprocess, sys, tempfile
from pathlib import Path
t = Path(tempfile.mkdtemp(prefix="contrib-unit-check-"))
atexit.register(shutil.rmtree, t, True)
CHK = Path(os.environ.get("CONTRIB_CHECK") or Path(os.path.realpath(sys.argv[1])).parent / "contrib-check")
SRC = CHK.read_text()
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


ID = ["-c", "user.name=u", "-c", "user.email=u@l", "-c", "commit.gpgsign=false"]
BIN = t / "bin"; BIN.mkdir()
(BIN / "gh").write_text("#!/bin/sh\necho '[]'\n"); (BIN / "gh").chmod(0o755)
PROFILES = t / "profiles"; PROFILES.mkdir()
LEDGER = t / "ledger"
XERJ = r"""REPO=x-org/x
REPO_DIR={repo}
UPSTREAM_REMOTE=upstream
BASE_BRANCH=main
CONTRIBUTOR=me
SENSITIVE_PATHS=(^|/)build\.rs$ (^|/)Cargo\.(toml|lock)$ (^|/)\.cargo/ (^|/)rust-toolchain ^\.github/ (^|/)\.git(attributes|modules)$ \.(sh|ps1|bash)$ ^scripts/ ^tools/
AREAS=^(engine/crates/[^/]+)
DOC_FILES=CHANGELOG.md engine/tests/es-compat-yaml/catch-lenient.txt
RATCHET_FILE=engine/tests/es-compat-yaml/catch-lenient.txt
"""
PYD = r"""REPO=p-org/p
REPO_DIR={repo}
USER_REPO_DIR=/home/u/p it's
UPSTREAM_REMOTE=upstream
BASE_BRANCH=main
CONTRIBUTOR=me
SETUP_KEY=uv.lock pyproject.toml core
SENSITIVE_PATHS=^\.github/ ^pyproject\.toml$ ^uv\.lock$
AREAS=^(pkg)/ ^(core)/ ^(docs)/ ^(tests)/
FORK_CI=1
"""
BASE_FILES = {
    "engine/crates/a/src/lib.rs": "a1\na2\na3\n", "engine/crates/a/src/other.rs": "o\n",
    "engine/crates/b/src/lib.rs": "b\n", "CHANGELOG.md": "# log\n\n- old\n",
    "engine/tests/es-compat-yaml/catch-lenient.txt": "keep\nlenient-1\nlenient-2\n",
    "pkg/a.py": "a = 1\n", "pkg/b.py": "b = 1\n", "core/c.py": "c = 1\n", "tests/t.py": "t = 1\n",
    "docs/d.md": "line 1\nline 2\n", "uv.lock": "lock 1\n", "pyproject.toml": "[p]\n",
}
n = 0


def write(root, files):
    for path, text in files.items():
        p = root / path
        if text is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
    git("add", "-A", cwd=root)
    git(*ID, "commit", "-qm", "c", cwd=root)


def case(profile, branch_files, base_files=None, repo_name="x"):
    """A fresh upstream, a pipeline clone with fix/<slug> on it, and a candidate; returns the slug."""
    global n
    n += 1
    slug = f"c{n}"
    up = t / f"up{n}"; clone = t / f"clone{n}"
    git("init", "-q", "-b", "main", str(up)); write(up, BASE_FILES)
    git("clone", "-q", "-o", "upstream", str(up), str(clone))
    base_sha = git("rev-parse", "HEAD", cwd=clone)
    git("checkout", "-q", "-b", f"fix/{slug}", cwd=clone); write(clone, branch_files)
    if base_files:
        write(up, base_files)
    repo = "x-org/x" if profile is XERJ else "p-org/p"
    (PROFILES / f"{repo.replace('/', '-')}.env").write_text(profile.format(repo=clone))
    cand = LEDGER / "candidates" / slug; cand.mkdir(parents=True)
    (cand / "state.json").write_text(json.dumps({"repo": repo, "branch": f"fix/{slug}", "base_sha": base_sha,
                                                 "issue": None, "started": "2026-01-01T00:00:00+00:00"}))
    return slug


ENV = dict(os.environ, PATH=f"{BIN}:{os.environ['PATH']}", CONTRIB_LEDGER=str(LEDGER),
           CONTRIB_PROFILE_DIR=str(PROFILES), GIT_CONFIG_NOSYSTEM="1")


def run(*args, src=None):
    path = CHK
    if src is not None:
        path = t / "mutant"; path.write_text(src)
    r = subprocess.run([sys.executable, "-I", str(path), *args], capture_output=True, text=True, env=ENV)
    return r.returncode, r.stdout + r.stderr


def verdict(slug, src=None):
    rc, out = run(slug, src=src)
    v = [l.split()[1] for l in out.splitlines() if l.startswith("VERDICT ")]
    return (v[-1] if v else "none"), out


LIB2 = {"engine/crates/a/src/lib.rs": "a1\nA2\na3\n"}
XCASES = {
    "x_unchanged": (dict(LIB2), None, "unchanged"),
    "x_sensitive": ({**LIB2, "engine/crates/a/build.rs": "fn main() {}\n"}, None, "needs-look"),
    "x_same_crate_moved": (dict(LIB2), {"engine/crates/a/src/other.rs": "o2\n"}, "retest-merge"),
    "x_other_crate_moved": (dict(LIB2), {"engine/crates/b/src/lib.rs": "b2\n"}, "unchanged"),
    "x_changelog_conflict": ({**LIB2, "CHANGELOG.md": "# log\n\n- mine\n- old\n"},
                             {"CHANGELOG.md": "# log\n\n- theirs\n- old\n"}, "rebase-docs"),
    "x_changelog_conflict_crate_moved": ({**LIB2, "CHANGELOG.md": "# log\n\n- mine\n- old\n"},
                                         {"CHANGELOG.md": "# log\n\n- theirs\n- old\n",
                                          "engine/crates/a/src/other.rs": "o2\n"}, "rebase-code"),
    "x_code_conflict": (dict(LIB2), {"engine/crates/a/src/lib.rs": "a1\nB2\na3\n"}, "rebase-code"),
    "x_ratchet_gone": ({**LIB2, "engine/tests/es-compat-yaml/catch-lenient.txt": "keep\nlenient-2\n"},
                       {"engine/tests/es-compat-yaml/catch-lenient.txt": "keep\nlenient-2\n"},
                       "merged-or-closed"),
}
for name, (mine, theirs, want) in XCASES.items():
    got, out = verdict(case(XERJ, mine, theirs))
    check(f"{name}: {want}" + ("" if got == want else f" (got {got}: {out[-400:]})"), got == want)

if os.environ.get("CONTRIB_CHECK_PIN_ONLY"):
    print("ALL PASS" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)

DOC = {"docs/d.md": "line 1\nline two\n"}
PCASES = {
    "p_setup_moved": (dict(DOC), {"uv.lock": "lock 2\n"}, "retest-merge"),
    "p_setup_dir_moved": ({"pkg/a.py": "a = 2\n"}, {"core/new.py": "n = 1\n"}, "retest-merge"),
    "p_same_area_moved": ({"pkg/a.py": "a = 2\n"}, {"pkg/b.py": "b = 2\n"}, "retest-merge"),
    "p_other_area_moved": ({"pkg/a.py": "a = 2\n"}, {"tests/t.py": "t = 2\n"}, "unchanged"),
    "p_sensitive": ({"pyproject.toml": "[p]\nx = 1\n"}, None, "needs-look"),
}
for name, (mine, theirs, want) in PCASES.items():
    got, out = verdict(case(PYD, mine, theirs))
    check(f"{name}: {want}" + ("" if got == want else f" (got {got}: {out[-400:]})"), got == want)

# --where: shell lines a POSIX shell can eval, quoting intact
slug = case(PYD, dict(DOC))
rc, out = run("--where", slug)
r = subprocess.run(["sh", "-c", out + '\nprintf "%s|%s|%s|%s" "$REPO" "$BRANCH" "$USER_REPO_DIR" "$FORK_CI"'],
                   capture_output=True, text=True)
check("where_evals", rc == 0 and r.stdout == f"p-org/p|fix/{slug}|/home/u/p it's|1")
rc, out = run("--where", "../" + slug)
check("where_bad_slug", rc == 2 and "bad slug" in out)


def home_test(src=None):
    """A path key's ~/ is the home folder, as contrib-run reads it; other keys keep their ~."""
    s2 = case(PYD.replace("USER_REPO_DIR=/home/u/p it's", "USER_REPO_DIR=~/p").replace("CONTRIBUTOR=me", "CONTRIBUTOR=~/me"),
              dict(DOC))
    rc, out = run("--where", s2, src=src)
    return rc == 0 and f"USER_REPO_DIR={ENV['HOME']}/p\n" in out and "CONTRIBUTOR='~/me'\n" in out


check("where_home", home_test())
DRV = Path(sys.argv[1]).read_text()
for line in ("PATH_KEYS = ", "HOME_WORD = "):
    mine = [x for x in SRC.splitlines() if x.startswith(line)]
    check(f"contrib-check's {line.split()[0]} is word for word the driver's",
          len(mine) == 1 and mine[0] in DRV.splitlines())


def where_quiet(src=None):
    """A failed --where prints nothing on stdout, so a caller's eval runs nothing."""
    path = CHK
    if src is not None:
        path = t / "mutant"; path.write_text(src)
    r = subprocess.run([sys.executable, "-I", str(path), "--where", "a'$(echo X)"], capture_output=True,
                       text=True, env=ENV)
    return r.returncode == 2 and r.stdout == "" and "bad slug" in r.stderr


check("where_fail_quiet", where_quiet())

# the profile checks: a missing key, and an AREAS regex with no group, stop with needs-look
(PROFILES / "p-org-p.env").write_text(PYD.replace("AREAS=", "#AREAS=").format(repo=t / "clone1"))
rc, out = run(slug)
check("profile_missing_key", rc == 2 and "has no AREAS" in out and "VERDICT needs-look" in out)
(PROFILES / "p-org-p.env").write_text(PYD.replace("^(pkg)/", "^pkg/").format(repo=t / "clone1"))
rc, out = run(slug)
check("areas_need_group", rc == 2 and "has no group" in out)
(PROFILES / "p-org-p.env").write_text(PYD.replace("^(pkg)/", "^(pkg/").format(repo=t / "clone1"))
rc, out = run(slug)
check("areas_bad_regex", rc == 2 and "is not a regex" in out)


# mutants: the script with one guard taken out; the guard's check must now fail
def mutant(name, old, new, test):
    global ok
    if SRC.count(old) != 1:
        print(f"FAIL mutant {name}: its text is not in contrib-check exactly once"); ok = False; return
    caught = not test(SRC.replace(old, new))
    print(("PASS " if caught else "FAIL ") + f"mutant {name} is caught"); ok &= caught


def setup_test(src):
    return verdict(case(PYD, dict(DOC), {"uv.lock": "lock 2\n"}), src=src)[0] == "retest-merge"


def area_test(src):
    return verdict(case(PYD, {"pkg/a.py": "a = 2\n"}, {"pkg/b.py": "b = 2\n"}), src=src)[0] == "retest-merge"


def slug_test(src):
    """../x would reach LEDGER/x, where a state.json is planted: only the slug check stops it."""
    (LEDGER / "x").mkdir(parents=True, exist_ok=True)
    (LEDGER / "x" / "state.json").write_text(json.dumps({"repo": "p-org/p", "branch": "fix/x"}))
    rc, out = run("--where", "../x", src=src)
    return rc == 2 and "SLUG=" not in out


def group_test(src):
    s2 = case(PYD, dict(DOC))
    (PROFILES / "p-org-p.env").write_text(PYD.replace("^(pkg)/", "^pkg/").format(repo=t / f"clone{n}"))
    rc, out = run(s2, src=src)
    return rc == 2 and "has no group" in out


mutant("setup_moved", "retest = bool(area_moved or setup_moved)", "retest = bool(area_moved)", setup_test)
mutant("area_moved", "retest = bool(area_moved or setup_moved)", "retest = bool(setup_moved)", area_test)
mutant("slug", 'if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", slug or ""):', "if False:", slug_test)
mutant("where_quiet", "out = sys.stderr if WHERE_MODE else sys.stdout", "out = sys.stdout", where_quiet)
mutant("home", "prof[k] = HOME_WORD.sub(lambda _: str(Path.home()), v) if k in PATH_KEYS else v", "prof[k] = v", home_test)
mutant("home_keys", "prof[k] = HOME_WORD.sub(lambda _: str(Path.home()), v) if k in PATH_KEYS else v",
       "prof[k] = HOME_WORD.sub(lambda _: str(Path.home()), v)", home_test)
mutant("areas_group", 'if key == "AREAS" and groups < 1:', "if False:", group_test)
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
