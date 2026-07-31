# Architecture

How the ecosystem-kit works: what gets installed, how the engine runs, which hooks may block, and how learning flows back into the kit.

## 1. Three layers

```
<project repo>
├── CLAUDE.md            POLICY    — auto-loaded, short, points into .memory/
├── .claude/             MACHINERY — kit-owned, refreshed by update.sh
│   ├── kit.json         per-project profile (seeded from kit profiles/, then project-owned)
│   ├── kit-version      kit version stamp (tracked)
│   ├── settings.json    hook wiring — cwd-independent commands ($CLAUDE_PROJECT_DIR)
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
3. open-entry counts for `VERIFY.md` and `ISSUES.md` — `- [ ]` checkboxes are the kit convention, but repos drift to plain dated bullets (`- YYYY-MM-DD — …`) and a checkbox-only counter then reports a confident **0 open** while real work piles up (meritick: 39 issues reported as none). When a file has no checkboxes, `count_open_entries()` falls back to counting dated bullets per *entry* — an entry runs from its bullet to the next one, and a shouted closure marker anywhere inside it (`Status: RESOLVED`, `DONE`, …; case-sensitive, so lowercase prose like "not done" stays open, and `PARTIALLY RESOLVED` stays open) closes it — and the banner flags the format drift rather than silently normalizing it
4. last 20 lines of **this branch's** diary entry, falling back to the most recently modified one (labelled as such, so a borrowed entry is never mistaken for the current change's record)
5. git branch, dirty-file count, unpushed-commit count
6. the `always_load` list from `kit.json` with the instruction to **Read each file before substantive work**

This works identically in headless runs (`claude -p`, CI, scheduled agents) — that is the headless bootstrap contract (see README). Agent templates reinforce it: every agent's First Steps require reading the `always_load` paths plus task-relevant `.memory/contexts/`.

## 3. Engine: daemon + client

```
settings.json ──► python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py" <hook>
                        │    ($CLAUDE_PROJECT_DIR = project root, set by Claude
                        │     Code on every hook run — wiring is cwd-independent)
                        │
                        ├─ Unix socket at .claude/hooks/.daemon.sock (0.5s connect / 45s response)
                        │        └─► _daemon.py: warm interpreter, EXEC_LOCK serialization,
                        │            discover_hook_modules() = glob(HOOKS_DIR/*.py) minus
                        │            _-prefixed (never a hardcoded roster)
                        └─ fallback: direct exec of the hook module (cold clone still enforces)
```

**Staleness changeover.** The daemon imports hook code once, so a daemon that predates an `update.sh` keeps enforcing the old rules (a stale `guard_protected_merge` wrongly blocked a feature-branch rebase, 2026-07-31). Every request compares `hooks_signature()` — (name, mtime_ns, size) over *all* `HOOKS_DIR/*.py`, `_`-prefixed internals included, since a hook's behavior changes when `_constants.py` does — against the signature captured at load:

1. On mismatch the daemon calls `retire_endpoint()` (unlink socket + PID file) **before** replying `Stale daemon: …`, then stops accepting. Retiring first matters: `cmd_start()` refuses to boot while a live PID file exists, so a successor could not start until the old process finished winding down.
2. `_client.py` treats the `Stale daemon:` prefix — like `Unknown hook:` — as a fall-back signal, never a hook block, and clears the auto-start cooldown so the very next call boots a fresh daemon instead of waiting out the rate limit.
3. That call runs the hook by direct exec against the **current on-disk code**, so the changeover neither blocks nor enforces stale rules.

`retire_endpoint()` is ownership-checked (the PID file must still name this process) so a retiring daemon can never unlink its successor's socket and strand a live daemon.

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
- **PreToolUse (Bash)**: on a `git commit`, if a `decision` or `discussion` flag is pending and the change's diary has not been touched since, **block (exit 2)**. Reasoning belongs in the diary at the commit that carries it — a diary written only at the Stop gate is a reconstruction, not a record. Deliberately narrow: a plain `code_change` never gates here (it rides to Stop), so ordinary commits are never interrupted. The `git commit` pattern is anchored to a command boundary (start, or after `;`/`&&`/`||`/`|`/newline) so `echo git commit` cannot wedge an unrelated command — a loose match matters more here than in advisory `guard_commit_message`, because this one blocks.
- **Stop**: while flags are pending, block until (a) the matching roster file (`code_change`→CHANGELOG.md, `decision`→DECISIONS.md, `discussion`→diary) has mtime newer than the flag, and (b) if `kit.diary`, the change's diary entry exists and was touched after the session's first flag. Satisfied flags are cleared; `stop_hook_active` guards against loops.

**Diary scope.** `diary_scope: "branch"` (the default) gives each branch/MR **one** diary — `.memory/diary/YYYY-MM-DD-<branch-slug>.md`, dated when that branch's diary started and reused for the branch's whole life, so a change's discussion and decisions stay together and survive the days it spans. An existing entry for the branch is reused whatever its date prefix; only the first write picks a date. `diary_scope: "daily"` keeps the legacy one-file-per-date behavior, and branch scope falls back to the dated file on a detached HEAD or outside a git repo (a diary keyed on a branch that doesn't exist is worse than a dated one). `docs_contract.py diary-path` resolves the current file so command flows never reimplement the rules.

### Profile-driven behavior

`kit.json` parameterizes the engine per project: `source_patterns` (docs_contract, tdd_gate), `domain_map` (context_attach, once-per-session state in `.memory/cache/`), `branch_types` + `protected_branches` (branch/merge guards), `principles` (guard_principles severity per check, `tdd: enforce` makes tdd_gate exit 2), `diary` + `diary_scope` (diary requirement and whether entries are per-branch or per-date). See `kit.config.example.md` for every key.

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
| `scripts/health-check.sh` → `.claude/scripts/` | overwrite always (kit-owned, same class as the engine) |
| `.claude/kit-version` | stamp |

`installer/update.sh TARGET_DIR` — refreshes **engine + scripts + skills only**, never `.memory/`, `kit.json`, or `settings.json`, and shows what changed.

**Wiring changes need the propagation path, not the update path.** Because `update.sh` never rewrites project-owned `settings.json`, a kit change that wires an *existing* hook onto a *new* event reaches installed repos as dead code — the module updates and nothing calls it, and `health-check`'s roster comparison still passes because the hook is wired on its other events. `tools/kit-propagate` closes this with a strictly additive policy patch (append a missing `(event, matcher, hook)` triple; never remove, reorder, or touch a matcher group the template doesn't define), alongside the attribution patch it already applies. When reviewing a change to `settings.json.template`, "does it work on a fresh install" is the wrong question: the installed base is the population that matters.

`scripts/health-check.sh` — kit.json valid + schema-conformant (python3), engine files present + py-compile, settings.json wiring == hook glob (name-token comparison), roster files exist, diary staleness warning >3 days, daemon status, and no `_client.py` wiring leaking into `~/.claude/settings.local.json`.

It is **installed into each target** at `.claude/scripts/health-check.sh` and refreshed by `update.sh`, so a repo checks itself against current kit conventions from a cold clone with no kit checkout present (the script is self-contained — it only reads `TARGET_DIR`). Without that refresh path a target keeps whichever copy it was installed with forever: DevContainer sat on a pre-`$CLAUDE_PROJECT_DIR` copy that flagged the kit's own canonical wiring as an ERR, pinning its score at a permanent red 85%.

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

Roster files each have a drain path so knowledge stays live instead of accreting: `/state` revalidates STATE.md against reality, `/verify` drains VERIFY checkboxes, `/summary` digests ISSUES + IDEAS + VERIFY + CHANGELOG into a top-3 next, `/diary` records the change as it happens (appending to the branch's entry at each decision, not once at the end), and `session_boot` re-surfaces staleness every morning.

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
