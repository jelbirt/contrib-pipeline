# Unit checks: the snapshot lists, for each open issue, the issues and PRs that mention it
# (fetch_issue_history), and the digests show them (## Linked from, the index's linked field), so
# a scout sees a maintainer's earlier "deferred" or "not planned" before it drafts a request.
# Usage: python3 -I unit_history.py <contrib-run>.
import atexit, json, os, re, shutil, subprocess, sys, tempfile, types, importlib.machinery, importlib.util
from pathlib import Path
t = Path(tempfile.mkdtemp(prefix="contrib-unit-history-"))
atexit.register(shutil.rmtree, t, True)
os.environ["CONTRIB_WORK"] = str(t / "work"); os.environ["CONTRIB_LEDGER"] = str(t / "ledger")
ld = importlib.machinery.SourceFileLoader("cr", sys.argv[1])
spec = importlib.util.spec_from_loader("cr", ld); m = importlib.util.module_from_spec(spec); ld.exec_module(m)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok &= bool(cond)
REPO = "own/repo"

def src(kind, n, state, repo=REPO, merged=False, reason=None, labels=(), title="t", opened="2025-08-03T00:00:00Z"):
    s = {"__typename": kind, "number": n, "title": title, "state": state, "createdAt": opened,
         "repository": {"nameWithOwner": repo}, "labels": {"nodes": [{"name": x} for x in labels]}}
    s.update({"merged": merged} if kind == "PullRequest" else {"stateReason": reason})
    return {"source": s}

TIMELINES = {
    1: {"totalCount": 9, "nodes": [
        src("PullRequest", 10, "CLOSED", labels=["deferred"], title="Old\nfix\n## Body"),
        src("Issue", 11, "CLOSED", reason="NOT_PLANNED", opened="2026-05-19T00:00:00Z"),
        src("PullRequest", 12, "MERGED", merged=True),
        src("PullRequest", 10, "CLOSED", labels=["deferred"]),          # the same PR again
        src("Issue", 5, "CLOSED", repo="other/x", reason="NOT_PLANNED"),  # another repo
        src("Issue", 1, "OPEN"),                                         # the issue itself
        {"source": None}, {"source": {"__typename": "Issue", "number": "7"}}]},
    2: {"totalCount": 4, "nodes": [
        src("PullRequest", 20, "OPEN"), src("Issue", 21, "OPEN", repo="OWN/Repo"),
        src("Issue", 22, "CLOSED", reason="REOPENED"), src("Issue", 23, "CLOSED")]},
}
calls = []
def fake_gh(*a):
    calls.append(a)
    assert a[:2] == ("api", "graphql") and "owner=own" in a and "name=repo" in a, a
    q = next(x for x in a if x.startswith("query="))
    asked = [int(n) for n in re.findall(r"\bi(\d+): issue\(number: \1\)", q)]
    if 3 in asked:
        raise RuntimeError("gh: Could not resolve to an Issue with the number of 3.")
    return json.dumps({"data": {"repository": {f"i{n}": {"timelineItems": TIMELINES[n]} for n in asked}}})

h = m.fetch_issue_history(fake_gh, REPO, [3, 1, 2, 0, -1, "4", 2, True], batch=2)
check("only positive int numbers are read", sorted(h) == ["1", "2", "3"])
check("two batches, and the failing one-issue batch is not retried", len(calls) == 2)
one = h["1"]
check("same-repo items only, the issue itself and repeats left out",
      [(i["kind"], i["number"]) for i in one["items"]] == [("pr", 10), ("issue", 11), ("pr", 12)])
check("states: closed unmerged, closed: not planned, merged",
      [i["state"] for i in one["items"]] == ["closed unmerged", "closed: not planned", "merged"])
check("labels and the opened day kept", one["items"][0]["labels"] == ["deferred"] and one["items"][1]["opened"] == "2026-05-19")
check("a title is one line", one["items"][0]["title"] == "Old fix ## Body")
check("other repos counted, not listed", one["other_repos"] == 1)
check("events past the page are counted", one["more"] == 1)
check("open PR and issue, repo name matched without case, reopened and reasonless closes are plain 'closed'",
      [i["state"] for i in h["2"]["items"]] == ["open", "open", "closed", "closed"])
check("a failed read is marked, not dropped", "Could not resolve" in h["3"].get("error", ""))

calls.clear()
h3 = m.fetch_issue_history(fake_gh, REPO, [1, 2, 3], batch=3)
check("a failed batch is retried one issue at a time", len(calls) == 4 and h3["1"] == h["1"] and h3["2"] == h["2"]
      and "error" in h3["3"])
for bad in ("not json", json.dumps({"data": {"repository": None}}), json.dumps({"errors": [{"message": "x"}]})):
    r = m.fetch_issue_history(lambda *a, b=bad: b, REPO, [1])
    check(f"an unusable reply marks the issue as not read: {bad[:24]}", set(r["1"]) == {"error"})
def refusing(exc):
    seen = []
    def gh(*a):
        seen.append(a); raise exc
    return gh, seen
for label, exc in (("a rate limit", RuntimeError("gh api graphql: API rate limit exceeded for user")),
                   ("a timeout", subprocess.TimeoutExpired(["gh"], 300))):
    gh, seen = refusing(exc)
    r = m.fetch_issue_history(gh, REPO, list(range(1, 101)), batch=40)
    check(f"{label} stops after one call and marks all 100 as not read",
          len(seen) == 1 and len(r) == 100 and all(set(v) == {"error"} for v in r.values()))
seen = []
def late_limit(*a):
    seen.append(a)
    if len(seen) > 1:
        raise RuntimeError("gh api graphql: API rate limit exceeded")
    return fake_gh(*a)
r = m.fetch_issue_history(late_limit, REPO, [1, 2, 5, 6, 7], batch=2)
check("a rate limit partway keeps what was read and marks the rest",
      len(seen) == 2 and r["1"] == h["1"] and r["2"] == h["2"]
      and all("rate limit" in r[k].get("error", "") for k in ("5", "6", "7")))
r = m.fetch_issue_history(lambda *a: json.dumps({"data": {"repository": {}}}), REPO, [1])
check("an issue missing from the reply is marked as not read", r["1"] == {"error": "not in the reply"})

# The digests
d = t / "gh"; d.mkdir()
issues = [{"number": n, "title": f"Issue {n}", "comments": []} for n in (1, 2, 3, 4, 6)]
m.write_json(d / "issues.json", issues)
for n in ("prs", "mine"):
    m.write_json(d / f"{n}.json", [])
hist = dict(h); hist["6"] = {"items": [], "other_repos": 0, "more": 0}
m.write_json(d / "history.json", hist)
m.write_digests(d, REPO)
idx = {l.split(" | ")[0]: l for l in (d / "issues.txt").read_text().splitlines() if l.startswith("#") and " | " in l}
check("index header names the field", "| labels | linked issues and PRs | title." in (d / "issues.txt").read_text())
check("index flags closed unmerged and not planned", "| linked 3 (2 closed unmerged or not planned) | Issue 1" in idx["#1"])
check("index shows a plain count when none is closed that way", "| linked 4 | Issue 2" in idx["#2"])
check("index marks an unread issue", "| linked ? | Issue 3" in idx["#3"] and "| linked ? | Issue 4" in idx["#4"])
md = (d / "issues" / "1.md").read_text()
check("the issue file lists the linked items", "## Linked from" in md
      and "- PR #10, closed unmerged, labels: deferred, opened 2025-08-03: Old fix ## Body" in md
      and "- issue #11, closed: not planned, opened 2026-05-19: t" in md and "- PR #12, merged, opened 2025-08-03: t" in md)
check("the list comes before the body", md.index("## Linked from") < md.index("## Body"))
check("a linked title cannot start a heading", md.splitlines().count("## Body") == 1)
check("more and other repos are said",
      "- and 1 more not listed: ask the driver for a `gh api repos/own/repo/issues/1/timeline --paginate` read" in md
      and "- and 1 from other repos, not listed" in md)
md3, md4 = (d / "issues" / "3.md").read_text(), (d / "issues" / "4.md").read_text()
check("a failed read says so and names the read to ask for",
      "- not read (gh: Could not resolve" in md3 and "`gh api repos/own/repo/issues/3/timeline --paginate`" in md3)
check("an issue missing from history.json says so", "- not read (missing): ask the driver" in md4)
check("no linked items reads as none", "## Linked from" in (d / "issues" / "6.md").read_text()
      and "\n- none\n" in (d / "issues" / "6.md").read_text())
(d / "history.json").unlink()
m.write_digests(d, REPO)
check("no history.json: not fetched", "- not fetched: ask the driver" in (d / "issues" / "1.md").read_text()
      and "| linked ? |" in (d / "issues.txt").read_text())

# A stub snapshot leaves no stale history behind
drv = m.Driver.__new__(m.Driver)
drv.args, drv.repo = types.SimpleNamespace(stub=True), REPO
m.write_json(d / "history.json", hist)
drv.snapshot(d)
check("a stub snapshot removes an old history.json", not (d / "history.json").exists()
      and (d / "issues.txt").exists())

# A real snapshot reads the history of the issues it listed
real = t / "real"
listed = [{"number": 1, "title": "One", "comments": []}, {"number": 2, "title": "Two", "comments": []}]
asked = []
def snap_gh(*a):
    asked.append(a[:2])
    if a[:2] == ("issue", "list"):
        return json.dumps(listed)
    if a[:2] == ("pr", "list"):
        return "[]"
    return fake_gh(*a)
drv.args, drv.prof, drv.gh = types.SimpleNamespace(stub=False), {"CONTRIBUTOR": "me"}, snap_gh
drv.snapshot(real)
hj = m.read_json(real / "history.json", None)
check("a real snapshot writes history.json for the listed issues",
      isinstance(hj, dict) and sorted(hj) == ["1", "2"] and hj["1"] == h["1"]
      and asked.count(("api", "graphql")) == 1
      and "| linked 3 (2 closed unmerged or not planned) | One" in (real / "issues.txt").read_text()
      and "- PR #10, closed unmerged" in (real / "issues" / "1.md").read_text())

print("UNIT HISTORY PASS" if ok else "UNIT HISTORY FAIL")
sys.exit(0 if ok else 1)
