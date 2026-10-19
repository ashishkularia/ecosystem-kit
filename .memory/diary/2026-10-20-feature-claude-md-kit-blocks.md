# 2026-10-20 — feature/claude-md-kit-blocks

## What the owner asked

PR #47 ended with a question: the kit has no way to deliver a CLAUDE.md template
change to installed repos — may it rewrite a marked block? Answer: yes.

## Why it was worth building rather than hand-editing five repos

`kit-propagate` has no CLAUDE.md handling and `update.sh` promised never to touch
it, so the scratch rule reached new installs only. Existing repos got the
directory and the skill fix — machinery — but not the sentence that tells Claude
to use them. Any future kit-wide policy would repeat that.

## Design

The template is the source of truth: `<!-- kit:begin NAME … -->` /
`<!-- kit:end NAME -->` inside `templates/CLAUDE.md.template`. `kit_blocks.py`
syncs each block. Absent → appended once; stale → exactly its begin..end lines
replaced; malformed → KEPT, file byte-identical. I chose markers over matching
on a heading because a project can rename a heading but a marker pair is an
explicit ownership statement, and the begin line says so in words.

## Things that went wrong or nearly did

- **The silent-discard trap was real, and I reproduced it.** `kit-propagate`
  stages `git add .claude <touched>` in a throwaway worktree. `update.sh` rewrote
  `CLAUDE.md` (repo root) and the old staging left it out: "CLAUDE.md staged: 0".
  The tool's own comment describes exactly this (2026-08-29, `.gitattributes`).
  Fixed by staging a TRACKED CLAUDE.md; tracked-only because `git add` refuses an
  ignored untracked path and takes the whole repo down.
- **The deployed `kit-propagate` is a copy.** `~/.claude/bin/kit-propagate` is
  byte-identical to `tools/kit-propagate` and is what cron runs, so this fix does
  nothing until `bootstrap-machine.sh` redeploys it. Worse than "nothing": a run
  before redeploy rewrites CLAUDE.md, drops it, advances the stamp, and the repo is
  not revisited until the next kit commit. I did NOT redeploy it myself (machine-
  level tool; owner action, logged in ISSUES).
- **A test that couldn't fail.** My "indented marker" lookalike had trailing prose
  after `-->`, so the end-anchored regex rejected it for the wrong reason and the
  mutant "indented markers recognised" survived. Fixed the test, added a second
  anchor mutant. Same lesson as the guard PR: assert the baseline passes, and
  check that a survivor is a weak test before calling the code fine.
- Path off-by-one in my own test (`dirname` x3 landed on `engine/`). The error
  message named the exact bad path, so it took one look.
- `update.sh`'s generic "To deliberately adopt the kit version of a KEPT file:
  install.sh --force" line is wrong for a KEPT CLAUDE.md block (install.sh skips an
  existing CLAUDE.md). The module's own line says "fix the markers by hand". Left
  as is — rewording the summary for one case is churn — but it is a rough edge.

## Re-delivery after the stack broke

This branch started as #49, stacked on #48 (itself stacked on #47). The owner merged
#47 into `main`, then #48 — but #48's base was still `chore/scratch-in-repo`, so the
guard exemption landed in that branch, not on `main`. Deleting #48's head branch then
auto-closed #49. Nothing was lost (every branch still existed), but `main` had the
scratch policy and not the `rm -rf` exemption.

Rebuilt without the stack: `git rebase origin/main` on this branch. Git dropped the
#47 commit as already applied; the #48 commit replays unchanged (its tree is
byte-identical to what the owner merged, checked with `git diff` against
`origin/chore/scratch-in-repo`), and this feature commit sits on top. One PR, two
commits, so one merge — no base branch for anyone to delete. The lesson is in
GOTCHAS: GitHub ignores `merge=union`, and a stack is a trap on top of that.

## Verification

30 tests, 18 mutants all killed against a passing baseline; 291 total green. Then
the real thing, in `.claude/scratch/`: simulated pre-block install with hand-
written rules around the gap → `update.sh` appended 25 lines, removed 0, original
bytes identical, second run a no-op → edited inside the block (reverted) and
outside (kept) → deleted an end marker (KEPT, update continued, file unchanged).

## Not done

- Redeploying `kit-propagate`; running it (opens PRs in five repos).
- A health-check rule for blocks — it runs in the target without the template and
  would have to hard-code block names.
- This repo's own CLAUDE.md is not kit-installed, so it carries no block; its
  scratch bullet is hand-written.
