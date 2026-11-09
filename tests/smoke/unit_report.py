# Unit checks for the user's reports: the packet's shape (rules/packet.md), QUEUE.md and SUMMARY.md.
import atexit, json, os, shutil, sys, tempfile, time, importlib.machinery, importlib.util
from pathlib import Path
t = Path(tempfile.mkdtemp(prefix="contrib-unit-report-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
drv = sys.argv[1]
ld = importlib.machinery.SourceFileLoader("cr", drv)
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)

example = (m.SKILL / "examples" / "packet.md").read_text()
check("the example packet passes its own rules", m.packet_problems(example) == [])
check("the example is within the word limit", len(m.prose(example).split()) <= m.PACKET_MAX_WORDS)
spec_text = (m.SKILL / "rules" / "packet.md").read_text()
check("the rules name every heading and row the driver checks",
      all(f"`## {h}`" in spec_text for h in m.PACKET_HEADINGS)
      and all(f"**{r}**" in spec_text for r in m.PACKET_ROWS) and str(m.PACKET_MAX_WORDS) in spec_text)

def problems_after(old, new):
    assert old in example, old
    return m.packet_problems(example.replace(old, new, 1))
check("a missing heading is named", any("'## Options'" in p for p in problems_after("## Options", "## Choices")))
check("a missing row is named", any("**Risk**" in p for p in problems_after("| **Risk** |", "| Risk |")))
check("a status other than ready is refused", any("Ready to publish." in p for p in
      problems_after("**Ready to publish.**", "**Needs your decision.**")))
check("a file:line pointer is refused", any("es_compat.rs:20099" in p for p in
      problems_after("## The fix\n", "## The fix\n\nSee es_compat.rs:20099.\n")))
check("a packet over the word limit is refused", any("over the limit" in p for p in
      problems_after("## Not covered\n", "## Not covered\n\n" + "word " * m.PACKET_MAX_WORDS + "\n")))
check("words inside diagrams do not count", m.packet_problems(example.replace(
      "```mermaid\n", "```mermaid\n%% " + "word " * m.PACKET_MAX_WORDS + "\n", 1)) == [])
check("a missing details link is named", any("details.md" in p for p in
      problems_after("(details.md)", "(notes.md)")))
for ok_text in ("es.example.com:9200", "`http.port:9200`", "thread_pool.search.size:13", "crates.io:443",
                "12:30", "v1.2:3", "localhost:9200"):
    check(f"ordinary text is not a pointer: {ok_text}", problems_after("## The fix\n", f"## The fix\n\nSee {ok_text}.\n") == [])
check("a #L pointer is refused", problems_after("## The fix\n", "## The fix\n\nSee path/to/search.rs#L120.\n") != [])
t0 = time.time(); m.packet_problems("a." * 200_000); m.POINTER_RE.search("a." * 1_000_000)
check("a long run of name characters is checked quickly", time.time() - t0 < 2)
check("a huge packet is refused by size before any pattern runs",
      "bytes" in m.packet_problems("x" * (m.PACKET_MAX_BYTES + 1))[0])
check("table pipes and markup are not words", m.packet_words(example) < len(m.prose(example).split())
      and m.packet_words("| **Area** | x |\n|---|---|\n## The fix") == 4)
check("one diagram is not enough", any("two mermaid" in p for p in
      problems_after("```mermaid", "```text")))

title, status = m.packet_head("# A [bad](link) | <b>`x`\\\n\n**Needs your decision.** Pick one.\n")
check("the queue's title and status are inert markdown",
      title == "A \\[bad\\](link) \\| \\<b\\>x\\\\" and status == "Needs your decision. Pick one.")
check("a question is inert markdown", m.md_text("[Answer](https://e) `contrib-run x`\nok", 800)
      == "\\[Answer\\](https://e) \\`contrib-run x\\` ok")
check("no title when the first line is not one", m.packet_head("text\n# Title\n") == (None, None))

# QUEUE.md: a ready candidate shows its packet's title and status; a needs-you one, its question
# and the command that answers it.
cands = m.LEDGER / "candidates"
def cand(slug, state, packet=None):
    d = cands / slug; (d / "session").mkdir(parents=True)
    (d / "state.json").write_text(json.dumps(state))
    if packet is not None:
        (d / "session" / "packet.md").write_text(packet)
cand("good-one", {"status": "ready", "title": "old title", "updated": "2"}, example)
cand("asks", {"status": "needs-you", "stage": "A", "title": "Asking", "question": "Keep the old\nlimit?",
              "updated": "1"}, "# Asking [x]\n\n**Needs your decision.** One question.\n")
cand("gone", {"status": "abandoned", "title": "No packet yet", "reason": "overlaps PR 12"})
cand("linked", {"status": "stopped", "title": "Linked [x]", "stop_reason": "deadline"})
(cands / "linked" / "session" / "packet.md").symlink_to(m.SKILL / "examples" / "packet.md")
cand("dir", {"status": "failed", "title": "A dir", "reason": "boom"})
(cands / "dir" / "session" / "packet.md").mkdir()
d = m.Driver.__new__(m.Driver); d.repo = "xerj-org/xerj"
d.rebuild_queue()
q = (m.LEDGER / "QUEUE.md").read_text()
check("a ready line uses the packet's title and status",
      "- [Cluster setting search.max_buckets is saved but ignored by searches](candidates/good-one/session/packet.md)"
      " (`good-one`): Ready to publish. 2 decisions need your OK." in q)
check("a needs-you entry shows its question and the answer command",
      "- [Asking \\[x\\]](candidates/asks/session/packet.md) (`asks`), stage A" in q
      and "  - **Question:** Keep the old limit?" in q
      and '`contrib-run --repo xerj-org/xerj --answer asks "..."`' in q)
check("a candidate with no packet falls back to its state",
      "- [No packet yet](candidates/gone/session/packet.md) (`gone`): overlaps PR 12" in q)
check("a symlinked or folder packet is not read", "- [Linked \\[x\\]](candidates/linked/session/packet.md)" in q
      and "- [A dir](candidates/dir/session/packet.md) (`dir`): boom" in q)

# SUMMARY.md: the plain top block comes first, the tables under Details.
d.run_id = "2026-01-01-000000"; d.run_dir = m.LEDGER / "runs" / d.run_id; d.run_dir.mkdir(parents=True)
d.t_start = time.time() - 600; d.stop_kind = None; d.stop_reason = "candidate limit reached (1)."
d.done = [("good-one", "ready"), ("asks", "needs-you")]
sess = cands / "good-one" / "sessions"; sess.mkdir()
(sess / f"C-{int(time.time())}.json").write_text(json.dumps(
    {"session_id": "s1", "total_cost_usd": 1.5, "num_turns": 3, "duration_ms": 120000}))
(cands / "good-one" / "results").mkdir()
(cands / "good-one" / "results" / "index.jsonl").write_text(json.dumps(
    {"at": m.now(), "kind": "test", "met": True, "secs": 300}) + "\n")
d.write_summary()
sm = (d.run_dir / "SUMMARY.md").read_text()
top = sm.split("## Details")[0]
check("the summary opens with outcomes, time and cost in plain words",
      "**1 ready for your review, 1 waiting on your decision.** 10 min, 1.50 USD." in top
      and "candidate limit reached (1). " not in top and "reached (1).." not in top
      and "candidate limit reached (1).\n" in top)
check("the summary links each packet by its title",
      "| Cluster setting search.max_buckets is saved but ignored by searches | ready for your review |"
      " [packet](../../candidates/good-one/session/packet.md) |" in top)
check("the summary splits session time from the driver's", "the sessions worked 2 min" in top
      and "took 5 min between their turns" in top)
check("the detailed tables follow under Details", "### Sessions" in sm.split("## Details")[1]
      and "### Driver requests" in sm.split("## Details")[1])
check("details.md is recorded with the packet", "details.md" in m.RECORD_TOP)
d.prof_md = "profile"
check("stages A and C get the spec and the example, B only the spec",
      all("## Example" in d.system_text(f) and "Ready to publish." in d.system_text(f)
          for f in ("A-investigate.md", "C-finish.md"))
      and "## Example" in d.system_text("B-fix.md") and "Ready to publish. 2 decisions" not in d.system_text("B-fix.md"))
# A FIFO swapped in after the size check must not hang the reader.
import stat as st_mod, threading
fifo = t / "fifo"; os.mkfifo(fifo); reg = t / "reg"; reg.write_text("x")
real_lstat = m.os.lstat
m.os.lstat = lambda p, *a, **k: real_lstat(reg)
box = []
th = threading.Thread(target=lambda: box.append(m.read_session_file(fifo)), daemon=True); th.start(); th.join(3)
m.os.lstat = real_lstat
check("a FIFO swapped in after the check is refused, not waited on", box == [None])
print("ALL PASS" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
