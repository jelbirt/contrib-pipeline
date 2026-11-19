#!/usr/bin/env bash
#
# pre-commit-guard.sh: PreToolUse(Bash) gate for agent-made commits.
#
# Enforces at the tool call what CLAUDE.md can only state:
#   1. scripts/checks.sh must pass in the tree being committed.
#   2. No agent commits on the default branch (main is the review inbox).
#
# Escapes, typed into the commit command itself so every override is deliberate
# and visible in the transcript:
#   SKIP_CHECKS=1 git commit ...        skip the green bar
#   ALLOW_MAIN_COMMIT=1 git commit ...  allow a commit on main
#
# THIS IS A GUARDRAIL FOR COOPERATING SESSIONS, NOT A SECURITY BOUNDARY. It is
# trivially bypassable by design and must never wedge unrelated work, so it
# fails OPEN on payload-level problems: unreadable JSON, missing node, git
# errors, a commit aimed at another repo. It does NOT fail open on a segment
# that will not tokenize: such a segment falls back to a conservative substring
# match and is treated as a commit.
#
# What actually reaches that fallback is an UNBALANCED QUOTE, such as an
# apostrophe in an unquoted argument. A multi-line `-m` message does NOT: both
# segments() and words() only break on a newline while outside quotes, so a
# newline inside quotes is ordinary content and the segment tokenizes cleanly.
# Do not "fix" segments() to split on quoted newlines; that would break the
# common case.
#
# PreToolUse contract: exit 0 allows, exit 2 blocks and feeds stderr back as the
# reason. ANY OTHER EXIT CODE LETS THE COMMIT THROUGH: a guard with the wrong
# exit code is a no-op that looks installed.
#
set -uo pipefail   # deliberately NOT -e: every failure path here is explicit.

DEFAULT_BRANCH="main"

payload="$(cat)" || exit 0
[ -n "$payload" ] || exit 0

command -v node >/dev/null 2>&1 || exit 0

SELF_REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# Resolve a directory to its git COMMON dir (shared by every worktree of a
# repo). Comparing toplevels instead would treat each worktree as a different
# repo and skip the gate everywhere it matters most.
common_dir() {
  local d="$1" out
  out="$(cd "$d" 2>/dev/null && git rev-parse --git-common-dir 2>/dev/null)" || return 1
  [ -n "$out" ] || return 1
  ( cd "$d" 2>/dev/null && cd "$out" 2>/dev/null && pwd ) || return 1
}

OUR_COMMON="$(common_dir "$SELF_REPO")" || exit 0

read -r -d '' PARSER <<'NODE'
const fs = require('fs'), path = require('path');
// `cd ~/repo && git commit` is ordinary usage, and path.resolve does NOT expand
// `~`: it yields /home/you/~/repo, which does not exist, so the hit is dropped
// and the commit goes ungated. A path built from a shell VARIABLE ($HOME/repo)
// stays unresolvable, since this parser does not run a shell. Known blind
// spots, both of which fail the same way as the bug above: $HOME/repo and
// ~user/repo. Rare enough in agent-written commands not to be worth parsing.
const HOME = process.env.HOME || require('os').homedir();
const expand = (p) => p === '~' ? HOME : (p.startsWith('~/') ? path.join(HOME, p.slice(2)) : p);
let raw = '';
try { raw = fs.readFileSync(0, 'utf8'); } catch (e) { process.exit(0); }
let tool = '', cmd = '', payloadCwd = '';
try {
  const j = JSON.parse(raw);
  tool = j.tool_name || '';
  cmd = (j.tool_input && j.tool_input.command) || '';
  payloadCwd = j.cwd || '';
} catch (e) { process.exit(0); }
if (tool !== 'Bash' || !cmd) process.exit(0);

// Anchor, in priority order:
//   1. the payload's `cwd`: the SESSION's working directory, which is where a
//      bare `git commit` actually lands. The Bash tool keeps a persistent cwd,
//      so a session that cd'd into a worktree must be judged against THAT tree,
//      not the project dir it started in.
//   2. GUARD_REPO from the environment, NOT argv: `node -e` does not occupy the
//      script slot, so process.argv[2] is undefined and an argv-based anchor
//      silently degrades to process.cwd().
const START = payloadCwd || process.env.GUARD_REPO || process.cwd();

// Split on shell operators that live outside quotes.
function segments(s) {
  const out = []; let cur = '', q = null, i = 0;
  while (i < s.length) {
    const c = s[i];
    if (q === "'") { if (c === "'") q = null; cur += c; i++; continue; }
    if (q === '"') {
      if (c === '\\') { cur += c + (s[i + 1] || ''); i += 2; continue; }
      if (c === '"') q = null;
      cur += c; i++; continue;
    }
    if (c === "'" || c === '"') { q = c; cur += c; i++; continue; }
    if (c === '\\') { cur += c + (s[i + 1] || ''); i += 2; continue; }
    if ((c === '&' && s[i + 1] === '&') || (c === '|' && s[i + 1] === '|')) { out.push(cur); cur = ''; i += 2; continue; }
    if (c === ';' || c === '\n' || c === '|' || c === '&') { out.push(cur); cur = ''; i++; continue; }
    cur += c; i++;
  }
  out.push(cur);
  return out;
}

// Word-split one segment. Returns null when quotes are unbalanced.
function words(s) {
  const out = []; let cur = '', has = false, q = null, i = 0;
  while (i < s.length) {
    const c = s[i];
    if (q === "'") { if (c === "'") q = null; else cur += c; has = true; i++; continue; }
    if (q === '"') {
      if (c === '\\' && '"\\$`'.includes(s[i + 1])) { cur += s[i + 1]; i += 2; has = true; continue; }
      if (c === '"') q = null; else cur += c;
      has = true; i++; continue;
    }
    if (c === "'" || c === '"') { q = c; has = true; i++; continue; }
    if (c === '\\') { if (s[i + 1] !== undefined) { cur += s[i + 1]; i += 2; } else i++; has = true; continue; }
    if (/\s/.test(c)) { if (has) out.push(cur); cur = ''; has = false; i++; continue; }
    cur += c; has = true; i++;
  }
  if (q) return null;
  if (has) out.push(cur);
  return out;
}

// git subcommands that create a commit on the current branch. `commit` is the
// only one that authors new code, so it is the only one that runs the bar,
// but ALL of them land on a branch, so all of them face the main-branch rule.
// CLAUDE.md says an agent never merges a PR; without `merge` here, the command
// that violates that most directly would be the one the guard cannot see.
const VERBS = ['commit', 'merge', 'cherry-pick', 'revert', 'am', 'pull', 'rebase'];

// Match a verb only as a WHITESPACE-DELIMITED token. \b is wrong here: hyphens
// and slashes are non-word characters, so /\bam\b/ matches inside a path like
// /home/i-am-here/repo, which in the fallback path resolved the verb to `am`
// and skipped the green bar, since only `commit` runs it.
const VERB_RE = new RegExp('(?:^|\\s)(' + VERBS.join('|') + ')(?=\\s|$)');

const ASSIGN = /^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/;
function assign(tok, env) {
  const m = ASSIGN.exec(tok);
  if (!m) return;
  const on = m[2] !== '' && m[2] !== '0';
  if (m[1] === 'SKIP_CHECKS') env.skip = on;
  if (m[1] === 'ALLOW_MAIN_COMMIT') env.allowMain = on;
}

const found = [];
function walk(src, cwd, env, depth) {
  if (depth > 4) return;
  for (const seg of segments(src)) {
    if (!seg.trim()) continue;
    const w = words(seg);
    if (w === null) {
      // Conservative fallback: never skip. Reached on an unbalanced quote, not
      // on a multi-line -m message: segments() and words() only break on a
      // newline while outside quotes, so a quoted newline is ordinary content.
      // The tokenizer gave up, so recover by regex what the walk would have
      // tracked: the target directory and the escapes. Missing the redirection
      // here would silently judge the HOOK'S OWN checkout instead of the tree
      // being committed, which reads as a pass when it is really a miss.
      const gpos = seg.search(/(^|\s)git(\s|$)/);
      if (gpos >= 0 && VERB_RE.test(seg)) {
        // Scan ONLY the regions where a real prefix or flag can live. Scanning
        // the whole segment would let a commit MESSAGE that merely mentions
        // `SKIP_CHECKS=1` or `-C /some/path` silently activate it, and an
        // apostrophe in ordinary prose ("don't") is what drops us here.
        const pre = seg.slice(0, gpos);              // assignments, `cd`
        const post = seg.slice(gpos);
        const vm = VERB_RE.exec(post);
        const gitHead = vm ? post.slice(0, vm.index) : post;     // git global flags only
        const verb = vm ? vm[1] : 'commit';                      // unknown -> strictest

        let fbCwd = cwd;
        const unquote = (s) => s.replace(/^['"]|['"]$/g, '');
        const mCd = /(?:^|[\s({])cd\s+([^\s;&|)]+)/.exec(pre);
        if (mCd) fbCwd = path.resolve(fbCwd, expand(unquote(mCd[1])));
        const mC = /(?:^|\s)-C\s+([^\s;&|]+)/.exec(gitHead);
        if (mC) fbCwd = path.resolve(fbCwd, expand(unquote(mC[1])));

        const fbEnv = { ...env };
        const esc = (name) => {
          const m = new RegExp('(?:^|\\s)' + name + '=(\\S*)').exec(pre);
          return m ? m[1] !== '' && m[1] !== '0' : false;
        };
        if (esc('SKIP_CHECKS')) fbEnv.skip = true;
        if (esc('ALLOW_MAIN_COMMIT')) fbEnv.allowMain = true;
        found.push({ cwd: fbCwd, verb, ...fbEnv });
      }
      continue;
    }
    let k = 0;
    const local = { ...env };
    for (;;) {
      if (w[k] === 'env') { k++; continue; }
      if (w[k] !== undefined && ASSIGN.test(w[k])) { assign(w[k], local); k++; continue; }
      break;
    }
    if (k >= w.length) { env.skip = local.skip; env.allowMain = local.allowMain; continue; }

    // Step over subshell / brace-group openers. Without this, `(cd wt && git
    // commit)` tokenizes its head as `(cd`, matches no branch, and the cd is
    // DROPPED, while the commit in the next segment is still reported, anchored
    // at the wrong tree. That reads as a clean pass with the target never tested.
    let head = w[k];
    // Compound-command keywords head a segment the same way an opener does:
    // `if ...; then git commit` tokenizes its head as `then` and would be
    // DROPPED, silently bypassing both the bar and the branch rule.
    while (head === '(' || head === '{' || head === 'then' || head === 'do' ||
           head === 'else' || head === '!' || head === 'command') { k++; head = w[k]; }
    if (head === undefined) continue;
    if (head[0] === '(' || head[0] === '{') head = head.replace(/^[({]+/, '');
    if (head === 'export') {
      for (let j = k + 1; j < w.length; j++) assign(w[j], env);
      continue;
    }
    if (head === 'cd') {
      const t = w[k + 1];
      if (t && !t.startsWith('-')) cwd = path.resolve(cwd, expand(t));
      continue;
    }
    if (head === 'sh' || head === 'bash' || head === 'zsh') {
      const ci = w.indexOf('-c', k);
      if (ci !== -1 && w[ci + 1] !== undefined) walk(w[ci + 1], cwd, local, depth + 1);
      continue;
    }
    if (head === 'eval') { walk(w.slice(k + 1).join(' '), cwd, local, depth + 1); continue; }
    if (head !== 'git') continue;

    let gi = k + 1, gitCwd = cwd;
    while (gi < w.length) {
      const a = w[gi];
      if (a === '-C') { if (w[gi + 1] !== undefined) gitCwd = path.resolve(gitCwd, expand(w[gi + 1])); gi += 2; continue; }
      if (a === '-c' || a === '--git-dir' || a === '--work-tree' || a === '--namespace') { gi += 2; continue; }
      if (a.startsWith('-')) { gi++; continue; }
      break;
    }
    // `--dry-run` is a read-only query: it neither commits nor merges.
    if (VERBS.includes(w[gi]) && !w.includes('--dry-run')) {
      found.push({ cwd: gitCwd, verb: w[gi], ...local });
    }
  }
}

walk(cmd, START, { skip: false, allowMain: false }, 0);
for (const f of found) {
  process.stdout.write(
    ['COMMIT', f.cwd, f.skip ? 1 : 0, f.allowMain ? 1 : 0, f.verb].join('\t') + '\n',
  );
}
NODE

hits="$(printf '%s' "$payload" | GUARD_REPO="$SELF_REPO" node -e "$PARSER" 2>/dev/null)" || exit 0
[ -n "$hits" ] || exit 0

while IFS=$'\t' read -r marker dir skip allow_main verb; do
  [ "$marker" = "COMMIT" ] || continue
  [ -d "$dir" ] || continue

  # Scope: only gate commits landing in THIS repo.
  tgt_common="$(common_dir "$dir")" || continue
  [ "$tgt_common" = "$OUR_COMMON" ] || continue

  # git commits happily from a subdirectory, but the bar lives at the worktree
  # root. Without this, `cd src && git commit` looks for src/scripts/checks.sh,
  # finds nothing, and fails open: passing without ever running a test.
  top="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || continue
  [ -n "$top" ] && dir="$top"

  # A detached HEAD has no branch, so the branch RULE is inapplicable, but the
  # bar is not, and `git commit` works fine there. Don't skip the whole entry.
  branch="$(git -C "$dir" symbolic-ref --short HEAD 2>/dev/null || printf '%s' '(detached)')"

  if [ "$branch" = "$DEFAULT_BRANCH" ] && [ "$allow_main" != "1" ]; then
    cat >&2 <<EOF
BLOCKED: 'git $verb' would write to the default branch ($DEFAULT_BRANCH).

main is the review inbox for this repo. Work on a workstream branch and merge
back via PR, and PRs are merged by the owner, not by an agent:

    git checkout -b {branch}

If this genuinely belongs on main, re-run it as:

    ALLOW_MAIN_COMMIT=1 git $verb ...
EOF
    exit 2
  fi

  # Only `commit` authors new code; merge/pull/revert/etc. face the branch rule
  # above but do not need the bar re-run.
  [ "$verb" = "commit" ] || continue

  if [ "$skip" = "1" ]; then
    continue
  fi

  # Prefer the target worktree's OWN checks.sh, so a branch that changes the
  # bar is judged by its own version. Missing script -> fail open.
  checks="$dir/scripts/checks.sh"
  [ -x "$checks" ] || continue

  # </dev/null: this loop's stdin is the `<<< "$hits"` here-string, and anything
  # under checks.sh that reads stdin would swallow the remaining hits, silently
  # skipping every commit after the first.
  if ! out="$( cd "$dir" && "$checks" </dev/null 2>&1 )"; then
    {
      echo "BLOCKED: scripts/checks.sh failed in $dir; the tree is not green."
      echo
      printf '%s\n' "$out" | tail -30
      echo
      echo "Fix the failure and re-run. To commit anyway: SKIP_CHECKS=1 git commit ..."
    } >&2
    exit 2
  fi
done <<< "$hits"

exit 0
