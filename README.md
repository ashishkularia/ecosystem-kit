# ecosystem-kit

One SDLC ecosystem, installed **by copy** into every project repo (mylantite, grade5, meritick, homelab, DevContainer), differentiated only by a per-project profile. The kit is the single source of truth for the machinery; each project owns its own knowledge.

## The three-layer model

| Layer | Lives at | Owned by | Contents |
|-------|----------|----------|----------|
| **Machinery (kit-owned)** | `<repo>/.claude/hooks/`, `skills/` | the kit — refreshed by `update.sh` | hook engine + skills |
| **Machinery (kit-seeded)** | `<repo>/.claude/` | the project after install — `update.sh` never touches these | `commands/`, `agents/`, `settings.json` wiring (skip-if-exists at install), `kit.json` profile (seeded once, project-owned) |
| **Knowledge** | `<repo>/.memory/` | the project (never touched by updates) | STATE, DECISIONS, ISSUES, IDEAS, GOTCHAS, CONVENTIONS, VERIFY, CHANGELOG, DOCS-CHANGELOG, `contexts/`, `references/`, `diary/`, `auto/`, `cache/` |
| **Policy** | `<repo>/CLAUDE.md` | the project | the auto-loaded durable-policy file; short, and points into `.memory/` |

Machinery is **copied, never symlinked** — every repo works standalone (clones, CI, containers, machines without the kit checked out). The cost is drift; `update.sh` and `.claude/kit-version` manage it.

Knowledge is **always in-repo**, including for the grade5 partnership repo (owner directive, 2026-07-23): everything the ecosystem learns about a project is stored in that project's `.memory/`, nowhere else.

## The always-loaded guarantee

The ecosystem loads at **every** session start, regardless of task. The `session_boot` hook (SessionStart) emits: project + profile name, the head of `.memory/STATE.md` (with a staleness warning past 7 days), open VERIFY/ISSUES counts, the tail of the newest diary entry, git status (branch / dirty files / unpushed commits), and the `always_load` list with the instruction to Read each file before substantive work.

### Headless bootstrap contract

The same guarantee holds for non-interactive sessions (`claude -p`, CI, scheduled agents): SessionStart fires there too, so a headless run gets the identical banner and `always_load` instruction with zero manual setup. Corollaries the kit commits to:

- `install.sh` is non-interactive and idempotent — safe in a bootstrap script, safe to re-run.
- Hook wiring in `settings.json` uses **relative** commands (`python3 .claude/hooks/_client.py <hook>`), so nothing depends on where the repo is cloned.
- The engine is stdlib-only Python 3 — no pip, no venv, no network needed to boot.
- If the hook daemon isn't running, `_client.py` falls back to direct execution; a cold clone still enforces every gate.

## The owner guardrail

**Claude never merges or writes to `main`/`master` — anywhere, in any repo.** Only the owner merges. This is enforced fail-closed by `guard_protected_merge` (git merge/rebase into protected branches, `gh pr merge`, push refspecs targeting protected branches, GitHub MCP write tools) and `guard_branch_naming` (protected names are never creatable). `/pr-babysit` shepherds a PR through checks and review comments but stops short of the merge button, always.

## Install

```bash
installer/install.sh <TARGET_DIR> <PROFILE_NAME>   # e.g. installer/install.sh ~/mylantite mylantite
```

Idempotent. Refuses non-git targets. Copies the engine (overwrite OK) and commands/agents/skills (skips project-customized files unless `--force`); seeds `.memory/` **only where missing** — it never clobbers knowledge; copies `profiles/<name>.json` → `.claude/kit.json` only if absent (after that the profile is project-owned); writes `settings.json` only if absent (otherwise prints a manual-merge diff); merges `autoMemoryDirectory` into `settings.local.json`; appends missing `.gitignore` lines; stamps `.claude/kit-version`. Then: restart the session and run `scripts/health-check.sh`.

## Update

```bash
installer/update.sh <TARGET_DIR>
```

Refreshes **engine + skills only** — never `.memory/`, never `kit.json` — and shows what changed. From inside a project, `/kit-update` pulls the kit repo, runs `update.sh`, and reviews the diff.

## Self-improvement loop

Session learnings flow `/retro` → `.memory/` roster files (GOTCHAS, CONVENTIONS, DECISIONS, references) → and, when a learning is general-purpose, a **kit promotion**: a change to the kit's own templates/engine that every project inherits on its next `update.sh`. See `docs/ARCHITECTURE.md`.

## Repo layout

```
engine/hooks/          hook engine (+ tests/ — unittest, stdlib-only; tests never installed)
templates/             memory roster, settings, CLAUDE.md, commands/, agents/, skills/
profiles/              per-project kit.json seeds (mylantite, grade5, meritick, homelab, devcontainer)
installer/             install.sh, update.sh
scripts/               health-check.sh
docs/ARCHITECTURE.md   how it all fits together
kit.config.example.json / .md   full schema example + key-by-key reference
.memory/               the kit's own knowledge (it eats its own dog food)
```
