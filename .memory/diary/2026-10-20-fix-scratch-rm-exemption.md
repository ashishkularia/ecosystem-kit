# 2026-10-20 — fix/scratch-rm-exemption

## What the owner asked

After PR #47 (scratch moves from /tmp into `.claude/scratch/`) left two decisions
open, the owner answered "Add the narrow exception" — the `rm -rf` exemption for
literal paths under `.claude/scratch/` — and approved the kit editing a marked
block in CLAUDE.md (separate branch, `feature/claude-md-kit-blocks`).

## The design problem

`guard_dangerous_commands` is a fail-closed blocker and checks each sub-command
independently, before any of them runs. A per-sub-command "is this path inside
scratch?" test is therefore defeatable inside one command line:
`ln -s ~ .claude/scratch/l && rm -rf .claude/scratch/l/Documents` — at check time
the link does not exist, the path looks inside scratch, and the second half then
deletes real files. So the exemption is decided on the WHOLE line: every part
must itself be a scratch `rm`.

Second decision: parse with one regex over `[A-Za-z0-9_./-]`, not shlex. A
tokenizer gives a second reading of the line (quotes, expansions) that can
differ from the shell's. With no metacharacter in the alphabet, the thing the
guard parses is the thing that runs. `>/etc/f` is the case that motivates it:
from a cwd inside scratch, a tokenizer would call `>/etc/f` an in-scratch path.

## What testing found

- **My first mutation run was meaningless.** The harness printed
  `baseline (unmutated): FAIL`, so every "KILLED" proved nothing. Cause: one of my
  own assertions expected `rm --no-preserve-root -rf x` to be blocked, but the
  UNMODIFIED guard allows it. The harness now refuses to run mutants unless the
  baseline passes.
- **That failure was a real, pre-existing hole.** The guard's two filesystem
  patterns anchor at `rm\s+-[a-z]*…`, so `rm -r -f x`, `rm --recursive --force x`,
  `rm -v -rf x` and `rm --no-preserve-root -rf x` all exit 0. Not caused by this
  change and not widened here (more blocking changes every installed repo); logged
  in ISSUES with the fix shape.
- **Four mutants survived the first valid run.** M5 (symlinked-scratch check) was
  dead code: I compare against the unresolved target, so containment already
  fails — removed the check, kept the tests, added a mutant for the real risk
  (resolving the target). M7 (newline guard) was only mostly redundant: Python's
  `$` matches before a trailing newline, so `rm -rf a\n&& rm -rf b` needed its own
  test. M13 (dash-led operand) only shows from a cwd inside scratch. M16 was a
  no-op mutant of mine, so I dropped it instead of claiming it.
- Final: 29 tests, 15 mutants, all killed against a passing baseline; 261 total.

## Live check

First live attempt was blocked — correctly. My one-liner chained
`mkdir && touch && ls && rm -rf && ls`, and the whole-line rule refuses any
`rm -rf` sharing a line with anything but scratch removals. Nothing ran (the
block is pre-execution). Redone as separate calls: create, then standalone
`rm -rf .claude/scratch/live-probe` — allowed. `rm -rf .claude/scratch/nope/..` —
blocked. That friction is the price of the whole-line rule and is documented.

## Not done

- The `rm -r -f` pattern gap (ISSUES).
- Installed repos keep their old guard until `/kit-update`; until then `rm -rf`
  on scratch is still blocked there and `rm -r` is the fallback (the template and
  the user-level CLAUDE.md say so).
