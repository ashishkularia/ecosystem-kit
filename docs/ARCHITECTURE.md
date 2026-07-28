# Architecture

How the ecosystem-kit works: what gets installed, how the engine runs, which hooks may block, and how learning flows back into the kit.

## 1. Three layers

```
<project repo>
├── CLAUDE.md            POLICY    — auto-loaded, short, points into .memory/
├── .claude/             MACHINERY — kit-owned, refreshed by update.sh
│   ├── kit.json         per-project profile (seeded from kit profiles/, then project-owned)
│   ├── kit-version      kit version stamp (tracked)
│   ├── settings.json    hook wiring — relative commands only
│   ├── settings.local.json  per-machine, untracked (autoMemoryDirectory → <repo>/.memory/auto)
│   ├── hooks/           engine copy (minus tests/)
│   └── commands/ agents/ skills/   templates copy, project-customizable
│                        (skip-if-exists at install; update.sh refreshes skills/ only)
└── .memory/             KNOWLEDGE — project-owned, NEVER touched by update.sh
    ├── STATE.md DECISIONS.md ISSUES.md IDEAS.md GOTCHAS.md
    ├── CONVENTIONS.md VERIFY.md CHANGELOG.md DOCS-CHANGELOG.md
    ├── contexts/ references/ diary/ auto/
    └── cache/           self-gitignored via a TRACKED cache/.gitignore ("*" + "!.gitignore",
                         so the dir survives clones) — hook session state lives here
```

Separation rationale: `update.sh` can refresh machinery aggressively because it is guaranteed never to touch knowledge. The profile (`kit.json`) sits in machinery territory but is seeded-once and project-owned thereafter — updates never overwrite it.

Everything is installed **by copy** (never symlink): each repo works standalone in clones, CI, and containers. Drift is managed, not prevented: `kit-version` + `update.sh` + `/kit-update`.

## 2. The always-loaded rule

The ecosystem is loaded at session start **regardless of task** — the user should never have to remember to "activate" it.

`session_boot` (SessionStart, fail-open) emits `hookSpecificOutput.additionalContext` containing:

1. project + profile name (from `kit.json`)
2. first 40 lines of `.memory/STATE.md`, plus a stale warning if its "Last validated" date is >7 days old
3. open `- [ ]` counts in `VERIFY.md` and `ISSUES.md`
4. last 20 lines of the newest `.memory/diary/*.md`
5. git branch, dirty-file count, unpushed-commit count
6. the `always_load` list from `kit.json` with the instruction to **Read each file before substantive work**

This works identically in headless runs (`claude -p`, CI, scheduled agents) — that is the headless bootstrap contract (see README). Agent templates reinforce it: every agent's First Steps require reading the `always_load` paths plus task-relevant `.memory/contexts/`.

## 3. Engine: daemon + client

```
settings.json ──► python3 .claude/hooks/_client.py <hook>
                        │
                        ├─ Unix socket at .claude/hooks/.daemon.sock (0.5s connect / 45s response)
                        │        └─► _daemon.py: warm interpreter, EXEC_LOCK serialization,
                        │            discover_hook_modules() = glob(HOOKS_DIR/*.py) minus
                        │            _-prefixed (never a hardcoded roster)
                        └─ fallback: direct exec of the hook module (cold clone still enforces)
```

- `_constants.py`: `HOOKS_DIR = dirname(realpath(__file__))`, `PROJECT_ROOT = dirname(dirname(HOOKS_DIR))`, `MEMORY_DIR = PROJECT_ROOT/.memory`, and `load_kit()` → `.claude/kit.json` with safe defaults for every key (missing/corrupt config degrades, never crashes).
- Daemon PID/log/socket files live in `HOOKS_DIR`, gitignored by the installer's snippet.
- Hook protocol: JSON payload on stdin; PreToolUse block = exit 2 + reason on stderr; advisory = exit 0 + guidance; Stop-gate = `{"decision":"block","reason":...}` on stdout, with the `stop_hook_active` loop-guard.

## 4. Fail-open vs fail-closed

The v1 flaw: any advisory hook bug blocked all tools. v2 splits the roster — on engine/hook **crash**, `_client.py` exits 0 with a stderr warning unless the hook is in `BLOCKING_HOOKS`:

| Hook | On crash | Why |
|------|----------|-----|
| `guard_dangerous_commands` | **fail CLOSED** (exit 2) | force-push / hard-reset / WHERE-less SQL must never slip through on a bug |
| `secret_scanner` | **fail CLOSED** | a leaked secret is unrecoverable |
| `guard_protected_merge` | **fail CLOSED** | the owner-only merge guarantee is absolute |
| `docs_contract` | **fail CLOSED** | the knowledge layer is the product; silent decay defeats the kit |
| `session_boot` | fail open | a broken banner must not block sessions |
| `context_attach` | fail open | advisory surfacing |
| `guard_file_writes` | fail open | blocks when *working*; crash must not lock all writes |
| `guard_branch_naming` | fail open | naming hygiene, defense-in-depth behind guard_protected_merge |
| `guard_principles` | fail open | advisory by design |
| `guard_commit_message` | fail open | advisory |
| `guard_post_test` | fail open | summarizer |
| `tdd_gate` | fail open | even under `tdd: enforce`, a crashed gate shouldn't block edits |

(Note the distinction: fail-open hooks still *block* when they run correctly and find a violation — the table is about crash behavior only.)

## 5. Hook roster and wiring

| Event | Hooks (in order) |
|-------|-------------------|
| SessionStart | `session_boot` |
| PreToolUse · Bash | `guard_dangerous_commands`, `guard_branch_naming`, `guard_protected_merge` |
| PreToolUse · Edit\|Write | `secret_scanner`, `guard_file_writes`, `tdd_gate` |
| PreToolUse · `mcp__github__.*` | `guard_protected_merge` (matcher catches every GitHub MCP tool; the hook itself filters to write/merge operations) |
| PostToolUse · Edit\|Write | `docs_contract`, `context_attach`, `guard_principles` |
| PostToolUse · Read | `context_attach` (domain docs surface on reads too, per its Edit\|Write\|Read contract) |
| PostToolUse · Bash | `guard_commit_message`, `guard_post_test` |
| Stop | `docs_contract` |

### docs_contract (the knowledge-decay stopper)

- **PostToolUse**: an Edit/Write matching `source_patterns` records a pending `code_change` flag in `.memory/cache/pending.json` (+ reminder). Command flows (`/decide`, `/idea`, discussions) may record `decision` / `discussion` flags the same way — flag names are accepted generically.
- **Stop**: while flags are pending, block until (a) the matching roster file (`code_change`→CHANGELOG.md, `decision`→DECISIONS.md, `discussion`→diary) has mtime newer than the flag, and (b) if `kit.diary`, today's `.memory/diary/YYYY-MM-DD.md` exists and was touched after the session's first flag. Satisfied flags are cleared; `stop_hook_active` guards against loops.

### Profile-driven behavior

`kit.json` parameterizes the engine per project: `source_patterns` (docs_contract, tdd_gate), `domain_map` (context_attach, once-per-session state in `.memory/cache/`), `branch_types` + `protected_branches` (branch/merge guards), `principles` (guard_principles severity per check, `tdd: enforce` makes tdd_gate exit 2), `diary` (Stop-gate diary requirement). See `kit.config.example.md` for every key.

## 6. Ceremony and gates

`ceremony.levels` maps each level (express / standard / full / critical) to gate IDs; `gates` defines each gate's name, prose pass-criteria, and mechanical commands (empty = judgment gate). The conductor classifies work into a level (using `ceremony.default` plus escalation signals such as touching auth/billing/exam paths), runs the level's gates, and applies the 3-strike retry rule before escalating to the owner. **Critical always ends with human review** — kit-wide rule, whatever the profile lists. Gate content is mined from the projects' own verification standards (e.g. MyLantite's G1–G7).

## 7. Installer and updater

`installer/install.sh TARGET_DIR PROFILE_NAME` — idempotent; refuses non-git targets. Copy semantics per layer:

| What | Semantics |
|------|-----------|
| engine (`hooks/`, minus tests) | overwrite always |
| commands / agents / skills | skip existing (project customizations win) unless `--force` |
| `.memory/` roster | seed **only missing** files — never clobber knowledge |
| profile → `.claude/kit.json` | copy only if missing |
| `settings.json` | write only if missing; else print manual-merge diff instruction |
| `settings.local.json` | merge `autoMemoryDirectory` via python3 (preserve other keys) |
| `.gitignore` | append missing snippet lines (`.claude/hooks/.daemon.*`, `.claude/hooks/__pycache__/`, `.claude/settings.local.json`; `kit-version` **is** tracked). `.memory/cache/` is NOT in the snippet — it self-ignores via a tracked `cache/.gitignore` (`*` + `!.gitignore`) so the dir survives clones; the installer scrubs the legacy root line and seeds `.gitkeep` into empty `diary/`/`auto/` |
| `.claude/kit-version` | stamp |

`installer/update.sh TARGET_DIR` — refreshes **engine + skills only**, never `.memory/` or `kit.json`, and shows what changed.

`scripts/health-check.sh` — kit.json valid + schema-conformant (python3), engine files present + py-compile, settings.json wiring == hook glob (name-token comparison), roster files exist, diary staleness warning >3 days, daemon status, and no `_client.py` wiring leaking into `~/.claude/settings.local.json`.

## 8. The self-improvement loop

```
work session
   │  corrections, surprises, decisions
   ▼
/retro ── distills into ──► .memory/  (GOTCHAS, CONVENTIONS, DECISIONS, references/, auto/)
   │
   │  "this learning is not project-specific"
   ▼
kit promotion ── PR against ecosystem-kit (template/engine/profile change)
   │                └─ owner merges (owner-only rule applies to the kit too)
   ▼
/kit-update in each project ── update.sh ──► every repo inherits the improvement
```

Roster files each have a drain path so knowledge stays live instead of accreting: `/state` revalidates STATE.md against reality, `/verify` drains VERIFY checkboxes, `/summary` digests ISSUES + IDEAS + VERIFY + CHANGELOG into a top-3 next, `/diary` closes the day, and `session_boot` re-surfaces staleness every morning.

## 9. Command, agent, and skill rosters

- **Commands**: `state`, `verify`, `issues`, `idea`, `decide`, `retro`, `summary`, `diary`, `pr-babysit` (loop: checks + review comments → fix → push; **never merges**), `kit-update`.
- **Agents**: `conductor` (orchestrates ceremony + gates), `architect`, `builder`, `reviewer`, `qa`, `ops`. Read-only roles (`conductor`, `architect`, `reviewer`, `qa`) carry `disallowedTools: [Edit, Write, NotebookEdit]` frontmatter — only `builder` (code) and `ops` (git/changelog) write. Every agent's First Steps: read the `always_load` paths + task-relevant `.memory/contexts/`.
- **Skills**: `adaptive-ceremony`, `discovery`, `planning`, `handoff`, `self-check`, `devils-advocate`, `fix-test-failures`.

## 10. Profiles at a glance

| Profile | Stack | merge_is_deploy | Notable |
|---------|-------|-----------------|---------|
| mylantite | laravel-react | **true** | G1–G7 gates via `docker exec mylantite_app`; TS-enum drift check; rich domain_map; auth/billing/exam ⇒ critical |
| grade5 | cloudflare-worker | **true** (portal) | partnership repo, knowledge in-repo by owner directive; marketing site has NO build step by rule |
| meritick | laravel-livewire | false | keeps `feat` branch type (existing history); Pest sqlite-fast + postgres-parity |
| homelab | ha-docs | false | `master` protected; `make lint-md`; source = MCP config mutations + dashboard YAML; tdd/logging off |
| devcontainer | infra-harness | false | clone-in hosting harness (containers + nginx vhost per project); gates = config validity + runtime health |

The "Notable" column is a paraphrase — each profile's `_note` field in `profiles/*.json` is the SSOT for these descriptions; update it there first.

## 11. Machine layer

Repo-level guardrails cannot stop a push issued outside any repo, so a thin machine layer — versioned in `tools/`, deployed per machine by `tools/bootstrap-machine.sh` — backs them up:

| Piece | Deployed to | Role |
|-------|-------------|------|
| deny permissions | `~/.claude/settings.local.json` | `git push` / `git config` / `git clean` and GitHub MCP merge tools denied machine-wide |
| `safe-push` | `~/.claude/bin` | the only allowed push path — refuses updates to an existing remote default branch, force pushes, and deletions; feature branches and first-publish allowed |
| `guard_protected_branch.py` | `~/.claude/hooks-machine` | PreToolUse guard wired against `mcp__github__*` tools in the machine settings |
| repo registry | `~/.claude/repo-registry` | one checkout path per line; the shared roster both cron tools read (`pr-comment-poller register <path>` manages it) |
| cron | user crontab | `weekly-hygiene` (Mon 06:07 — headless `.memory/` drain loops, doc-only, never pushes) and `pr-comment-poller` (every 15 min, 07–23h — headless `claude -p` run when new owner comments land on an open PR) |

`bootstrap-machine.sh` is idempotent and rebuilds all of the above from the kit checkout in one run; its manual steps (SSH key, PAT, Claude login, repo registration) each run a confirm → verify → retry loop, so a fresh machine converges in a single pass. Re-run it after a kit update to refresh the deployed tools.
