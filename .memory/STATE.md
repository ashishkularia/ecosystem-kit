# STATE — ecosystem-kit

Last validated: 2026-08-01

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
  mylantite/meritick caches. Engine unittest suite 94/94 green (re-run
  2026-08-01). The former rollout blocker is cleared —
  `~/.claude/settings.local.json` now carries only the machine-level branch
  guard, zero legacy `_client.py` wirings.
- Machine layer live: crons for weekly-hygiene (today's per-repo logs present
  in every target's `.memory/cache/`), pr-comment-poller, pr-rebase,
  kit-propagate (daily update PRs into targets; owner merges), and
  prune-stale-branches (06:52).

## Invariants

- Install is copy-only — no symlinks, ever.
- `update.sh` never touches `.memory/` or `.claude/kit.json`.
- Installer seeds `.memory/` roster only where missing; re-running is always safe.
- Claude never merges or writes to main/master anywhere — owner merges.
- Engine is stdlib-only Python; all shell JSON work goes through python3 (no jq).
