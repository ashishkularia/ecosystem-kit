# ecosystem-kit

One SDLC ecosystem, installed **by copy** into every project repo (mylantite, grade5, meritick, homelab, DevContainer), differentiated only by a per-project profile. The kit is the single source of truth for the machinery; each project owns its own knowledge.

## The three-layer model

| Layer | Lives at | Owned by | Contents |
|-------|----------|----------|----------|
| **Machinery (kit-owned)** | `<repo>/.claude/hooks/`, `skills/`, `scripts/` | the kit — refreshed by `update.sh` | hook engine, skills, health-check |
| **Machinery (kit-seeded)** | `<repo>/.claude/` | the project after install — `update.sh` refreshes only what the project has NOT edited | `commands/`, `agents/`, `settings.json` wiring (skip-if-exists at install), `kit.json` profile (seeded once, project-owned) |
| **Knowledge** | `<repo>/.memory/` | the project (never touched by updates) | STATE, DECISIONS, ISSUES, IDEAS, GOTCHAS, CONVENTIONS, VERIFY, CHANGELOG, DOCS-CHANGELOG, `contexts/`, `references/`, `diary/`, `auto/`, `cache/` |
| **Policy** | `<repo>/CLAUDE.md` | the project | the auto-loaded durable-policy file; short, and points into `.memory/` |

Machinery is **copied, never symlinked** — every repo works standalone (clones, CI, containers, machines without the kit checked out). The cost is drift; `update.sh` and `.claude/kit-version` manage it.

Knowledge is **always in-repo**, including for the grade5 partnership repo (owner directive, 2026-07-23): everything the ecosystem learns about a project is stored in that project's `.memory/`, nowhere else.

## The always-loaded guarantee

The ecosystem loads at **every** session start, regardless of task. The `session_boot` hook (SessionStart) emits: project + profile name, the head of `.memory/STATE.md` (with a staleness warning past 7 days), open VERIFY/ISSUES counts, the tail of this branch's diary entry, git status (branch / dirty files / unpushed commits), and the `always_load` list with the instruction to Read each file before substantive work.

### Headless bootstrap contract

The same guarantee holds for non-interactive sessions (`claude -p`, CI, scheduled agents): SessionStart fires there too, so a headless run gets the identical banner and `always_load` instruction with zero manual setup. Corollaries the kit commits to:

- `install.sh` is non-interactive and idempotent — safe in a bootstrap script, safe to re-run.
- Hook wiring in `settings.json` uses **cwd-independent** commands (`python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py" <hook>`) — Claude Code sets `$CLAUDE_PROJECT_DIR` to the project root on every hook run, so nothing depends on where the repo is cloned *or* on the session's current working directory.
- The engine is stdlib-only Python 3 — no pip, no venv, no network needed to boot.
- If the hook daemon isn't running, `_client.py` falls back to direct execution; a cold clone still enforces every gate.

## Published artifacts land in the repo

Artifacts are authored in the session scratchpad, which is wiped when the session ends — so publishing produced a live URL and nothing you could review, diff, or edit later. The `artifact_sync` hook (PostToolUse · Artifact) mirrors every publish into `docs/artifacts/<slug>/`: the **source file verbatim** (the one you edit), a **generated counterpart** in the other format, and `artifact.json` with the live URL. An `INDEX.md` lists them all.

To change an artifact, edit its source file in the repo and republish it with its URL — the live page and the committed copy stay in step. Only the source is authoritative; generated files carry a "do not edit" banner, because the kit is stdlib-only and neither conversion direction is faithful.

**Viewing them.** An artifact source is a *fragment* — the host supplies the HTML skeleton at publish time — so it is not openable on its own. Each directory therefore gets a generated `index.html`, and the root gets a gallery, which makes the whole tree a static site with no build step:

```bash
npx serve docs/artifacts     # or: python3 -m http.server -d docs/artifacts
```

By default each publish makes its own commit, scoped to the artifact paths alone and never on a protected branch. Configure with the `artifacts` key in `kit.json`.

## The owner guardrail

**Claude never merges or writes to `main`/`master` — anywhere, in any repo.** Only the owner merges. This is enforced fail-closed by `guard_protected_merge` (git merge/rebase into protected branches, `gh pr merge`, push refspecs targeting protected branches, GitHub MCP write tools) and `guard_branch_naming` (protected names are never creatable). `/pr-babysit` shepherds a PR through checks and review comments but stops short of the merge button, always.

The guarantee also holds outside any repo, via the machine layer (`tools/`, deployed by `tools/bootstrap-machine.sh`): deny-permissions on raw `git push` and GitHub MCP merge tools in `~/.claude/settings.local.json`, `safe-push` in `~/.claude/bin` as the only push path (never an existing remote default branch, never force, never delete), `guard_protected_branch.py` in `~/.claude/hooks-machine` wired against GitHub MCP tools, and the shared repo registry (`~/.claude/repo-registry`) driving the `weekly-hygiene` and `pr-comment-poller` cron jobs. See `docs/ARCHITECTURE.md` §11.

## Install

```bash
installer/install.sh <TARGET_DIR> <PROFILE_NAME>   # e.g. installer/install.sh ~/mylantite mylantite
```

Idempotent. Refuses non-git targets. Copies the engine (overwrite OK) and commands/agents/skills (skips project-customized files unless `--force`); seeds `.memory/` **only where missing** — it never clobbers knowledge; copies `profiles/<name>.json` → `.claude/kit.json` only if absent (after that the profile is project-owned); writes `settings.json` only if absent (otherwise prints a manual-merge diff); merges `autoMemoryDirectory` into `settings.local.json`; appends missing `.gitignore` lines; stamps `.claude/kit-version`. Then: restart the session and run `scripts/health-check.sh`.

## Update

```bash
installer/update.sh <TARGET_DIR>
```

Refreshes **engine, skills, scripts** — plus any command or agent still byte-identical to the kit template it was installed from, so kit improvements actually reach installed repos. Anything the project edited is reported `KEPT` and left alone; never `.memory/`, never `kit.json`, never `settings*.json`. Shows exactly what changed. If the kit has added a NEW hook, `settings.json` is project-owned and is never edited — so update.sh reports the unwired hook and prints the exact block to paste, rather than leaving it silently inert. From inside a project, `/kit-update` pulls the kit repo, runs `update.sh`, and reviews the diff.

## Self-improvement loop

Session learnings flow `/retro` → `.memory/` roster files (GOTCHAS, CONVENTIONS, DECISIONS, references) → and, when a learning is general-purpose, a **kit promotion**: a change to the kit's own templates/engine that every project inherits on its next `update.sh`. See `docs/ARCHITECTURE.md`.

## Repo layout

```
engine/hooks/          hook engine (+ tests/ — unittest, stdlib-only; tests never installed)
templates/             memory roster, settings, CLAUDE.md, commands/, agents/, skills/
profiles/              per-project kit.json seeds (mylantite, grade5, meritick, homelab, devcontainer)
installer/             install.sh, update.sh
scripts/               health-check.sh
tools/                 machine layer: safe-push, weekly-hygiene, pr-comment-poller, mcp-audit,
                       guard_protected_branch.py, bootstrap-machine.sh (deploys it all)
docs/ARCHITECTURE.md   how it all fits together
kit.config.example.json / .md   full schema example + key-by-key reference
.memory/               the kit's own knowledge (it eats its own dog food)
```
