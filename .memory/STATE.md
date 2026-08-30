# STATE — ecosystem-kit

Last validated: 2026-08-31

## What this repo is

Single source of truth for the Claude SDLC ecosystem that gets installed BY COPY
into every project repo. Registered targets (machine registry
`~/.claude/repo-registry`, confirmed readable this run — see note below):
`/home/ubuntu/DevContainer` and its NESTED checkouts
`DevContainer/{mylantite,grade5,meritick}`, plus `/home/ubuntu/homeassistant`
(homelab profile), **plus this repo itself** (`/home/ubuntu/ecosystem-kit`,
a sixth registry line). `/home/ubuntu/grade5` is only a convenience symlink into
DevContainer, not a second install. `kit-propagate` explicitly skips its own
path when walking the registry (`tools/kit-propagate:399`), so self-registration
never triggers a kit-into-itself update PR — but `pr-comment-poller`,
`pr-rebase` and `prune-stale-branches` carry no such skip, so those three now
act on this repo directly too. `profiles/percale.json` (added 2026-08-30) is a
sixth PROFILE but deliberately NOT in the registry yet — it has no git remote,
and kit-propagate needs one to open a PR against (see ISSUES).
Machinery lands in `<repo>/.claude/`, knowledge lives in `<repo>/.memory/`.
Projects are differentiated ONLY by a per-project profile (`profiles/*.json`
copied to `.claude/kit.json`, project-owned thereafter). The ecosystem is
always loaded at session start via the `session_boot` SessionStart hook,
regardless of task.

## Layout

- `engine/hooks/` — Python hook engine (stdlib only) + `tests/` (unittest; never installed)
- `templates/` — settings.json, settings.local.json, CLAUDE.md, gitignore snippet,
  memory roster templates, commands, agents, skills, contexts README, references
- `profiles/` — mylantite, grade5, meritick, homelab, devcontainer, percale kit.json profiles
- `installer/` — `install.sh TARGET_DIR PROFILE` (full install, idempotent, never
  clobbers knowledge) and `update.sh TARGET_DIR` (engine+skills refresh only)
- `scripts/health-check.sh [TARGET_DIR]` — generic v2 health check for any installed repo
- `tools/` — machine-layer automation, deployed to `~/.claude/bin` +
  `~/.claude/hooks-machine` by `bootstrap-machine.sh`: safe-push,
  weekly-hygiene, pr-comment-poller, pr-rebase, kit-propagate,
  prune-stale-branches, guard_protected_branch.py
- `.memory/` — the kit's own dog-food memory (this file)

## Current state

- kit v1.0.0 ROLLED OUT: installed in all five true target repos, every
  `.claude/kit-version` stamped from a real kit commit and re-verified LIVE
  this run — DevContainer @ `f774d17`, mylantite/grade5/meritick/homeassistant
  @ `6b3a963`, all dated 2026-08-30 — all on the cwd-independent
  `$CLAUDE_PROJECT_DIR` hook wiring. *(This run's `~/.claude/repo-registry`,
  per-repo `kit-version`, and `crontab -l` reads all succeeded — the sandbox
  block that froze cross-repo claims at 2026-08-01 across four straight
  headless runs (see ISSUES 2026-08-03) did NOT reproduce this time. Treat
  this as one data point, not a confirmed policy change; re-test next run
  before relying on it.)*
- Engine unittest suite 210/210 green (was 164 on 2026-08-24 — 46 new tests
  landed this week alongside `artifact_sync`). 13 hook modules / 17 event
  wirings in this repo's own `.claude/settings.json` (was 12/16 — the new
  module is `artifact_sync.py`), both counts still consistent with each other.
- Machine layer confirmed live this run via `crontab -l`: weekly-hygiene
  (Mon 06:07), pr-comment-poller (`*/15` 07-23), kit-propagate (06:37, daily
  update PRs into the five true targets; owner merges), pr-rebase (08/12/16/20),
  prune-stale-branches (06:52) — all five entries present, unchanged from the
  2026-08-01 baseline.
- **Not a quiet week** — reverses the last two runs' pattern: 13 substantive
  commits landed 2026-08-27→2026-08-30 (vs. zero 2026-08-17→2026-08-24).
  Highlights: `artifact_sync` shipped (mirrors published artifacts into the
  repo, gitignore-blindspot detection, gallery-commit fix, optional
  `artifacts.deploy_command` auto-deploy to the homelab host), `gh` promoted to
  a machine-layer prerequisite with a real credential check (`verify_gh`),
  `kit-propagate` hardened four separate times (stale tracking-ref prune,
  orphaned-branch retry, a `check=False` fix so one repo's push refusal can't
  kill the whole run, `origin`-based stamp reads, deployed-copy staleness
  warning), a `merge=union` git-attribute added kit-wide so the append-only
  ledgers (CHANGELOG/DECISIONS/DOCS-CHANGELOG/diaries) stop conflicting on
  concurrent branches, `pr-rebase` fixed to poll GitHub's async
  `mergeable_state` instead of guessing, and `profiles/percale.json` added
  (sixth profile, pre-stack/pre-remote, deliberately unregistered). Full
  detail in CHANGELOG.
- Git: `main` clean, 0 dirty files, **up to date with `origin/main`** (0
  ahead / 0 behind) — the stacked-unpushed-hygiene-commit backlog flagged
  2026-08-17/08-24 (ISSUES) is cleared; everything through `9a9a362` is on the
  remote.

## Invariants

- Install is copy-only — no symlinks, ever.
- `update.sh` never touches `.memory/` or `.claude/kit.json`.
- Installer seeds `.memory/` roster only where missing; re-running is always safe.
- Claude never merges or writes to main/master anywhere — owner merges.
- Engine is stdlib-only Python; all shell JSON work goes through python3 (no jq).
