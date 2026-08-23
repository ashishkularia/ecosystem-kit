# STATE — ecosystem-kit

Last validated: 2026-08-24

## What this repo is

Single source of truth for the Claude SDLC ecosystem that gets installed BY COPY
into every project repo. Registered targets (machine registry
`~/.claude/repo-registry`): `/home/ubuntu/DevContainer` and its NESTED checkouts
`DevContainer/{mylantite,grade5,meritick}`, plus `/home/ubuntu/homeassistant`
(homelab profile). `/home/ubuntu/grade5` is only a convenience symlink into
DevContainer, not a second install.
Machinery lands in `<repo>/.claude/`, knowledge lives in `<repo>/.memory/`.
Projects are differentiated ONLY by a per-project profile (`profiles/*.json`
copied to `.claude/kit.json`, project-owned thereafter). The ecosystem is
always loaded at session start via the `session_boot` SessionStart hook,
regardless of task.

## Layout

- `engine/hooks/` — Python hook engine (stdlib only) + `tests/` (unittest; never installed)
- `templates/` — settings.json, settings.local.json, CLAUDE.md, gitignore snippet,
  memory roster templates, commands, agents, skills, contexts README, references
- `profiles/` — mylantite, grade5, meritick, homelab, devcontainer kit.json profiles
- `installer/` — `install.sh TARGET_DIR PROFILE` (full install, idempotent, never
  clobbers knowledge) and `update.sh TARGET_DIR` (engine+skills refresh only)
- `scripts/health-check.sh [TARGET_DIR]` — generic v2 health check for any installed repo
- `tools/` — machine-layer automation, deployed to `~/.claude/bin` +
  `~/.claude/hooks-machine` by `bootstrap-machine.sh`: safe-push,
  weekly-hygiene, pr-comment-poller, pr-rebase, kit-propagate,
  prune-stale-branches, guard_protected_branch.py
- `.memory/` — the kit's own dog-food memory (this file)

## Current state

- kit v1.0.0 ROLLED OUT (verified 2026-08-01): installed in all five
  registered repos, every `.claude/kit-version` stamped from a real kit commit
  (7e0d2d8 or 59916b5), all on the cwd-independent `$CLAUDE_PROJECT_DIR` hook
  wiring; engine hooks confirmed producing live-session artifacts in
  mylantite/meritick caches. The former rollout blocker is cleared —
  `~/.claude/settings.local.json` now carries only the machine-level branch
  guard, zero legacy `_client.py` wirings. *(Cross-repo claims above are
  frozen at the 2026-08-01 verification — this and subsequent weekly-hygiene
  runs check only what's readable from inside this repo's sandbox; see
  ISSUES for the scope note.)*
- Engine unittest suite 164/164 green (re-run 2026-08-24, unchanged from
  2026-08-17 — no engine commits landed this week either). 12 hook modules /
  16 event wirings in this repo's own `.claude/settings.json`, both counts
  still consistent with each other and unchanged since 2026-08-03.
- Machine layer live (as of 2026-08-01; not re-checked this run — see
  ISSUES): crons for weekly-hygiene, pr-comment-poller, pr-rebase,
  kit-propagate (daily update PRs into targets; owner merges), and
  prune-stale-branches (06:52).
- Since 2026-08-01: shell-syntax bypass in `guard_protected_merge` closed (18
  forms), hook-wiring now propagates additively via `kit-propagate`, diaries
  scoped per-branch/MR and enforced at commit time, the cross-repo promotion
  bar rewritten to be present-tense/evidence-based, and `tools/pr-thread`
  added for in-thread PR replies + marker-gated resolve. Full detail in
  CHANGELOG. **Third quiet week running**: zero substantive commits between
  2026-08-17 and 2026-08-24 — the only commit in that window is the 2026-08-17
  hygiene run's own `.memory` commit (`2dbf17a`). That commit was never
  pushed: `main` (`2dbf17a`) sits 1 commit ahead of `origin/main` (`5766bd6`)
  at this run's start, unlike the previous two weeks where the prior hygiene
  commit had already landed on the remote by the time this check ran. This
  run's own hygiene commit adds a second unpushed commit on top — hygiene
  commits are pushed by a separate step (or the owner), not by this run (see
  CONVENTIONS: owner-only merges/pushes to main); the backlog is expected to
  clear whenever that next push happens, not evidence of a process break.

## Invariants

- Install is copy-only — no symlinks, ever.
- `update.sh` never touches `.memory/` or `.claude/kit.json`.
- Installer seeds `.memory/` roster only where missing; re-running is always safe.
- Claude never merges or writes to main/master anywhere — owner merges.
- Engine is stdlib-only Python; all shell JSON work goes through python3 (no jq).
