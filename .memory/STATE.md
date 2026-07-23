# STATE — ecosystem-kit

Last validated: 2026-07-23

## What this repo is

Single source of truth for the Claude SDLC ecosystem that gets installed BY COPY
into every project repo (mylantite, grade5, meritick, homelab, DevContainer).
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
- `.memory/` — the kit's own dog-food memory (this file)

## Current state

- kit v1.0.0 authored 2026-07-23; installer/updater/health-check verified
  end-to-end against the REAL engine+templates for all five profiles in
  scratch git repos (install, re-run idempotency, update scope, drift
  detection, error paths); engine unittest suite 90/90 green. Not yet
  installed into any real project repo; rollout is blocked on cleaning the
  legacy `_client.py` wiring out of `~/.claude/settings.local.json` (ISSUES).

## Invariants

- Install is copy-only — no symlinks, ever.
- `update.sh` never touches `.memory/` or `.claude/kit.json`.
- Installer seeds `.memory/` roster only where missing; re-running is always safe.
- Claude never merges or writes to main/master anywhere — owner merges.
- Engine is stdlib-only Python; all shell JSON work goes through python3 (no jq).
