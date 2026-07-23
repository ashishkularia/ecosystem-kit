# kit.json — key-by-key reference

JSON cannot carry comments, so this file documents every key of `kit.config.example.json` (and therefore of every `profiles/*.json` and every installed `<repo>/.claude/kit.json`). The engine reads the file via `load_kit()` in `_constants.py`, which supplies a safe default for **every** key — a missing or malformed key never crashes a hook, it just disables the behavior that key drives.

| Key | Type | Default if missing | Meaning |
|-----|------|-------------------|---------|
| `kit_version` | string | `"0.0.0"` | Version of the kit the profile was authored against. Stamped by the installer into `.claude/kit-version`; `update.sh` compares against it. |
| `project` | string | repo dirname | Human name of the project. Echoed by `session_boot` in the session banner. |
| `stack` | string | `"generic"` | Short stack tag (`laravel-react`, `cloudflare-worker`, `ha-docs`, ...). Informational — agents use it to pick idioms; no hook branches on it. |
| `_note` | string | — | Free-text annotation, **ignored by the engine**. Carries owner directives and repo quirks that must travel with the profile (e.g. grade5's "partnership repo — everything in-repo" directive). Any `_`-prefixed key is treated the same way. |
| `protected_branches` | string[] | `["main", "master"]` | Branches Claude may **never** merge into, rebase onto, push to, or create. Enforced fail-closed by `guard_protected_merge` (git + `gh` + GitHub MCP write tools) and by `guard_branch_naming` (cannot create a branch by these names). Only the owner merges. |
| `branch_types` | string[] | `["feature","fix","hotfix","bugfix","chore","docs","refactor","test","revert"]` | Allowed `<type>/` prefixes for new branches; `guard_branch_naming` warns on other prefixes (advisory, exit 0) and hard-blocks only the creation of protected-branch names. Add legacy prefixes here (meritick keeps `feat` because existing branches use it) rather than fighting history. |
| `merge_is_deploy` | bool | `false` | `true` means merging to a protected branch triggers a production deploy (mylantite, grade5 portal). Agents treat PRs as release artifacts: `pr-babysit` gets stricter, reviewers assume prod blast radius. No hook branches on it directly — it is policy context. |
| `ceremony.default` | string | `"standard"` | Ceremony level assumed when the conductor has no signal to escalate/de-escalate. |
| `ceremony.levels` | object | all levels → `[]` | Maps each level (`express`, `standard`, `full`, `critical`) to the gate IDs that must PASS at that level. `critical` additionally always implies **mandatory human review** — that rule is kit-wide and not encoded per-profile. |
| `gates` | object | `{}` | Gate catalog. Each entry: `name` (short label), `desc` (pass/fail criteria in prose — this is what a reviewer agent checks against), `commands` (shell strings run from the repo root; empty array = judgment gate with no mechanical check). Gate IDs are free-form but `G1..Gn` is the convention; every ID referenced in `ceremony.levels` must exist here. |
| `containers` | object | `{}` | Logical role → container name (`{"app": "mylantite_app"}`). Lets agents and commands say "run in the app container" without hardcoding names. Empty for host-run projects. |
| `quality_commands` | object | all four → `[]` | Exactly four keys: `format`, `lint`, `typecheck`, `test`. Each an array of shell strings run from the repo root. This is what `/verify`-style flows and builder agents run between edits; gate `commands` may repeat them with stricter flags (`pint` vs `pint --test`). |
| `source_patterns` | string[] (Python regexes) | `[]` | What counts as **app source**, matched against repo-relative paths. Drives `docs_contract` (source edit ⇒ pending `code_change` flag ⇒ CHANGELOG + diary before stop) and `tdd_gate` (source edited with zero test edits ⇒ reminder, or exit 2 under `tdd: enforce`). Negative lookaheads are fine — the engine uses Python `re`. Keep these tight: false positives create reminder fatigue. |
| `domain_map` | array | `[]` | `[{"pattern": regex, "docs": [repo-rel paths]}]`. When an edited/read path matches `pattern`, `context_attach` surfaces each doc once per session. Docs that don't exist yet are silently skipped — it is normal to map a domain to a `.memory/contexts/` file that gets written later as knowledge accretes. |
| `always_load` | string[] | `[]` | Repo-relative paths that `session_boot` instructs the agent to Read before any substantive work, **every session, regardless of task**. This is the always-loaded guarantee; every profile should list at least `.memory/STATE.md`, but keep the list short (3-ish files) or it becomes noise that gets skipped. |
| `principles.tdd` | `"enforce"\|"advise"\|"off"` | `"advise"` | `enforce`: `tdd_gate` exits 2 when source is edited with no matching test edits this session. `advise`: reminder only. `off`: silent. |
| `principles.fail_fast` | same | `"advise"` | `guard_principles` flags error-swallowing (bare `except`, empty `catch`). |
| `principles.logging` | same | `"advise"` | Flags `print()` / `console.log` in non-test source when the project has a logger. Set `off` for docs/infra repos where the check is meaningless. |
| `principles.dead_code` | same | `"advise"` | Flags large commented-out code blocks. (Unreferenced-new-file heuristic exists but ships OFF.) |
| `principles.dry_kiss` | same | `"advise"` | Advisory text only — no mechanical check. |
| `file_write_rules` | object | `{"blocked": [], "allowed": []}` | Extra rules for `guard_file_writes` on top of its project-agnostic defaults. `blocked`: regexes (either `"<regex>"` or `["<regex>", "<reason>"]` pairs) that block writes; `allowed`: regexes that override blocks (both kit defaults and profile-added). Matched against repo-relative paths. |
| `diary` | bool | `true` | When `true`, the Stop-gate side of `docs_contract` also requires today's `.memory/diary/YYYY-MM-DD.md` to exist and be touched after the session's first pending flag. |

## Conventions that are kit-wide (not per-profile keys)

- **Owner-only merges**: Claude never merges or writes to `main`/`master` anywhere, in any repo, full stop. `protected_branches` configures *which* branches; the rule itself is not configurable.
- **Critical ⇒ human review**: the `critical` ceremony level always ends with owner sign-off, whatever gates it lists.
- **Paths are repo-relative** everywhere in this file; hooks normalize absolute paths before matching.
- **Profiles are seeds**: the installer copies `profiles/<name>.json` to `<repo>/.claude/kit.json` only if missing. After that the file is project-owned — edit it in the project, and promote generally-useful changes back to the kit profile via `/retro` → `/kit-update`.
