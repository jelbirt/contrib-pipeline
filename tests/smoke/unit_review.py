# Unit checks for stage C's review gate (review_check) and the citation check (citation_problems).
import atexit, json, os, shutil, sys, tempfile, time, importlib.machinery, importlib.util
from pathlib import Path
t = Path(tempfile.mkdtemp(prefix="contrib-unit-review-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
os.environ["CONTRIB_TRANSCRIPTS"] = str(t / "tr")
drv = sys.argv[1]
ld = importlib.machinery.SourceFileLoader("cr", drv)
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)

SID = "5fbda3e5-dfe7-4a2f-8665-484082f8e812"
REPORT = "## Review\n\n" + "The change counts buckets once after the merge and refuses over the limit. " * 6

def driver():
    d = m.Driver.__new__(m.Driver)
    d.cand = t / "cand"
    shutil.rmtree(d.cand, ignore_errors=True)
    (d.cand / "results").mkdir(parents=True)
    (d.cand / "session").mkdir()
    (d.cand / "sessions.json").write_text(json.dumps({"C": SID}))
    (d.cand / "state.json").write_text(json.dumps({"status": "running"}))
    d.prof = {}
    return d

def write_tr(lines):
    p = t / "tr" / "proj" / f"{SID}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(o) + "\n" for o in lines))

def use(uid, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": uid, "name": "Agent",
            "input": {"subagent_type": "code-reviewer", "prompt": "review the branch", **inp}}]}}

def result(uid, tur, kind="user", text=REPORT):
    o = {"type": kind, "message": {"content": [{"type": "tool_result", "tool_use_id": uid,
         "content": [{"type": "text", "text": text}]}]}}
    if tur is not None:
        o["toolUseResult"] = tur
    return o

done = {"status": "completed", "agentType": "code-reviewer", "totalToolUseCount": 9,
        "content": [{"type": "text", "text": REPORT}]}
launched = {"status": "async_launched", "isAsync": True}

# Run 2's stage C: the reviewer was launched in the background, and Claude Code later wrote an
# api-request copy of the conversation that repeats the call and its result with no toolUseResult.
d = driver()
write_tr([use("u1", run_in_background=True), result("u1", launched, text="Async agent launched"),
          use("u1", run_in_background=True), result("u1", None, kind="api-request-blob")])
why = d.review_check()
check("a background reviewer is not a review, even when a later copy repeats it", "background" in why)
check("the refusal tells the session to run it in the foreground", "foreground" in why)

d = driver()
write_tr([use("u1"), result("u1", launched, text="Async agent launched")])
check("a launch notice without the flag is not a review either", "background" in d.review_check())

d = driver()
write_tr([use("u1"), result("u1", done)])
check("a finished foreground review is usable", d.review_check() == "")
rt = (d.cand / "results" / "review-transcript.md").read_text()
check("its report is copied for the user", "counts buckets once" in rt and "1 usable" in rt)

d = driver()
write_tr([use("u1"), result("u1", done), result("u1", launched, kind="api-request-blob")])
check("a later copy cannot replace a real result", d.review_check() == "")

d = driver()
edit = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "e1", "name": "Edit",
        "input": {"file_path": "/elsewhere/src/lib.rs"}}]}}
write_tr([use("u1"), result("u1", done), edit, dict(edit, type="api-request-blob")])
d.review_check()
st = json.loads((d.cand / "state.json").read_text())
check("an edit after the review is counted once, not once per copy", st.get("review", {}).get("changes_after") == 1)

# Each guard on its own, since they back each other up.
d = driver()
write_tr([use("u1"), result("u1", None, kind="api-request-blob")])
check("a result only in another line type is not a result", "no result" in d.review_check())

d = driver()
write_tr([use("u1"), result("u1", launched, text="Async agent launched"), result("u1", None)])
check("a second result for the same call cannot replace the first", "background" in d.review_check())

d = driver()
write_tr([use("u1"), result("u1", done), edit, edit])
d.review_check()
check("a call repeated in a conversation line counts once",
      json.loads((d.cand / "state.json").read_text()).get("review", {}).get("changes_after") == 1)

d = driver()
write_tr([use("u1", run_in_background=True), result("u1", done)])
check("a reviewer asked to run in the background is refused even when it reports done", "background" in d.review_check())

d = driver()
write_tr([use("u1"), result("u1", {"isAsync": True})])
check("isAsync alone marks a background reviewer", "background" in d.review_check())

d = driver()
pointer = "This agent's report was delivered to you as a message from the agent (its handback call)."
write_tr([use("u1"), result("u1", dict(done, content=[{"type": "text", "text": pointer}], handback="send",
                                       handbackReport={"text": REPORT}), text=pointer)])
check("a report handed back as a message is read", d.review_check() == "")

d = driver()
bg = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "g1", "name": "Agent",
      "input": {"subagent_type": "general-purpose", "prompt": "x", "run_in_background": True}}]}}
write_tr([bg, result("g1", launched), use("u0", run_in_background=True), result("u0", launched),
          use("u1"), result("u1", done)])
check("the foreground review after them is usable", d.review_check() == "")
check("background agents started before the review count as changes after it",
      json.loads((d.cand / "state.json").read_text()).get("review", {}).get("changes_after") == 2)

# The citation check: a profile pattern keeps reference-source files out of what goes public.
pat = m.load_env(m.SKILL / "profiles" / "xerj-org-xerj.env").get("PUBLIC_FORBID_RE", "")
check("the xerj profile sets a citation pattern", bool(pat))
d = driver(); d.prof = {"PUBLIC_FORBID_RE": pat}
at_base = {"TestSegmentReader.java"}
d.cgit = lambda *a, check=True, **k: ("x.rs" if a[0] == "grep" and a[a.index("-e") + 1] in at_base else "")
def diff(*lines, path="engine/src/x.rs"):
    return "\n".join([f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}", "@@ -1 +1 @@", *lines])
def cp(log="", body="", d_text=""):
    return d.citation_problems(log, body, d_text, "base")
check("plain text passes", cp("fix(api): honour search.max_buckets\n\nES refuses with a 400.",
                              "Nothing cited here.", diff("+// ES counts the kept buckets once.")) == [])
check("a Java file in a commit message is refused",
      any("commit message" in p for p in cp(log="see MultiBucketConsumerService.java:109-130")))
check("a Java file in the PR body is refused", any("PR_BODY" in p for p in cp(body="as in DelayedBucket.java#L55")))
new = cp(d_text=diff("+// from server/src/main/java/org/x/YBuilder.java:62"))
check("a new Java file in an added line is refused, naming the file",
      any("engine/src/x.rs" in p and "YBuilder.java" in p for p in new))
check("a Java file the change moves is not new",
      cp(d_text=diff("-/// see SpanNearQueryBuilder.java:62", "+/// see SpanNearQueryBuilder.java:62, reworded")) == [])
check("a Java file already in the base is not new (test data)",
      cp(d_text=diff('+    {"title": "TestSegmentReader.java"}')) == [])
check("a host name is not a Java file", cp(log="see https://jdk.java.net/21/") == [])
check("a class name without the file is fine", cp(log="as Lucene's BooleanClause does") == [])
check("an added line that starts like a file header is still checked",
      any("YBuilder.java" in p for p in cp(d_text=diff("+++ see YBuilder.java"))))
many = cp(d_text=diff(*[f"+// N{k}.java" for k in range(d.CITATION_NAMES_CHECKED + 1)]))
check("past the cap the rest is reported, not passed",
      any("were checked" in p for p in many) and sum("adds a citation" in p for p in many) == d.CITATION_NAMES_CHECKED)
t0 = time.time(); cp(d_text=diff("+" + "a" * 1_000_000)); took = time.time() - t0
check(f"a 1 MB word is searched quickly ({took:.2f} s)", took < 1)
d.prof = {}
check("no pattern, no check", cp("Y.java:1", "Y.java", diff("+Y.java")) == [])
d.prof = {"PUBLIC_FORBID_RE": "("}
check("a broken pattern is reported, not raised", any("not a valid pattern" in p for p in cp("x")))

# final_checks runs it.
d = driver(); d.prof = {"PUBLIC_FORBID_RE": pat}
for f in ("packet.md", "details.md", "PR_BODY.md"):
    (d.sdir / f).write_text("x\n")
d.review_check = lambda: ""
d.git_dir_check = lambda *a, **k: None
d.st = lambda: {"base_sha": "base", "branch": "fix/x"}
def fake_git(*a, check=True, **k):
    return {"symbolic-ref": "refs/heads/fix/x", "log": "fix: per Foo.java:3", "rev-list": "abc"}.get(a[0], "")
d.cgit = fake_git
check("final_checks runs the citation check", any("cites reference source" in p for p in d.final_checks()))

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
