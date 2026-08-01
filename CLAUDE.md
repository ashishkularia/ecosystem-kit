# CLAUDE.md — ecosystem-kit

Durable policy for working in this repo. The kit ships the SDLC ecosystem to every project repo; bugs here propagate everywhere, so the bar is higher than in any single project.

## Hard rules

- **Stdlib-only Python.** Engine, installer helpers, tests: Python 3 standard library only. No pip, no venv, no third-party imports — target machines get no installs. Tests use `unittest` (pytest may not exist on the host).
- **Copy, never symlink.** The installer copies files into target repos. Never "optimize" this into symlinks or shared paths — every installed repo must work standalone (clones, CI, other machines). Drift is handled by `update.sh` + `.claude/kit-version`, not by sharing.
- **Cwd-independent hook wiring.** `templates/settings.json.template` commands are always `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py" <hook>` — Claude Code sets `$CLAUDE_PROJECT_DIR` to the project root on every hook run, so the command resolves regardless of the shell's cwd. Never hardcoded absolute paths, never per-machine paths, and never bare-relative (`python3 .claude/...` breaks the moment a session's persistent cwd leaves the repo root).
- **Fail-open by default, fail-closed for the four blockers.** Only `guard_dangerous_commands`, `secret_scanner`, `guard_protected_merge`, `docs_contract` may exit 2 on engine crash. Every other hook that crashes must exit 0 with a stderr warning. Do not add a hook to `BLOCKING_HOOKS` casually — an advisory hook bug must never block all tools (that was the v1 flaw).
- **No hardcoded hook rosters.** `_daemon.py` derives `HOOK_MODULES` by globbing `engine/hooks/*.py` (excluding `_`-prefixed). Adding a hook = adding a file + wiring it in the settings template. `health-check.sh` compares wiring against the glob.
- **No AI attribution anywhere, ever.** Owner rule (2026-07-29): no `Co-Authored-By:`, no `Claude-Session:`, no "Generated with Claude Code", no 🤖 line, no session URL — on commits, PR titles/bodies, PR comments, issues, or code comments. Nothing addressing Claude, the model, or Anthropic. Projects get this from `settings.json.template`'s `attribution` block; **this repo is not kit-installed**, so `.claude/settings.json` pins it here directly — but treat that as a backstop, not the rule. The rule holds even when a harness default says otherwise.
- **Owner-only merges.** Claude never merges or writes to `main`/`master` — in this repo too. Branch, push, PR; the owner merges.
- **No secrets anywhere.** Not in templates, not in profiles, not in test fixtures.
- **Schema discipline.** `profiles/*.json` conform exactly to the schema in `kit.config.example.json` / documented in `kit.config.example.md`. New keys land in the example + doc + `load_kit()` defaults **in the same change**, or not at all. `_`-prefixed keys are the only free-form escape hatch.

## The docs contract applies here too

This repo runs the ecosystem on itself (`.memory/` at the root is real, not a fixture). Any substantive change lands with:

- a line in `.memory/CHANGELOG.md`
- decisions → dated one-liner in `.memory/DECISIONS.md` (the *why*, not just the what)
- today's `.memory/diary/YYYY-MM-DD.md` entry
- engine behavior changes → matching update in `docs/ARCHITECTURE.md` and, if user-visible, `README.md`

## Testing changes

- Engine tests live in `engine/hooks/tests/` (`python3 -m unittest discover engine/hooks/tests`). They are excluded from installs.
- Hooks are stdin-JSON programs: test them by piping payload fixtures, asserting exit codes (0 advisory / 2 block) and output. Stop-gate hooks assert on the `{"decision":"block",...}` JSON and the `stop_hook_active` loop-guard.
- Before releasing: run health-check against a scratch install (`install.sh /tmp/<scratch-repo> <profile>`) — installer changes are only proven by installing.

## When a project needs something the kit doesn't do

Resist per-project forks of engine files. The order of preference: (1) a `kit.json` key that configures it, (2) a template the project customizes (commands/agents/skills are skip-if-exists), (3) only then an engine change — which every project inherits. Record the decision in `.memory/DECISIONS.md`.

## Promotion: a second EXISTING repo, today — not a future one

**If another existing repo could implement this process right now — or already has its own version of it — it belongs in the kit** (owner rule, 2026-08-01). The bar is *more than one* repo, not every repo.

The test is **present-tense and evidence-based: name the repo.** Not "will something need this one day?" but *"which existing repo could adopt this today, or is already doing it separately?"* If you cannot name one, it is not a promotion — it is a guess.

Ask it *actively*, not passively: whenever a process, recipe, guard, script or runbook is built or fixed, check the other repos before closing the work. Do they have the same shape? The same trap? Their own copy already?

- **A future need is not a reason to promote.** If a second repo might want it later, leave it where it is; promote it when that repo actually needs it. Nothing is lost by waiting — it is the same work done with evidence instead of a prediction, and it is what keeps a shared kit from accreting artifacts nobody uses and everybody must read past.
- **Existing duplication is the strongest signal, and means the kit is late.** Two repos already solving the same problem separately is not a reason to consider promotion; it is proof the promotion is overdue. Three forked copies of `split_shell_commands` lived in this engine, only one had learned to extract `$(…)`, and the gap let a push reach a protected branch.
- **Applicability is not universality.** Self-hosted-runner guidance serves two of five repos and no more; it qualifies because *both of those two run runners today*. Gate a kit artifact by relevance at use time (a skill that no-ops where it doesn't apply), never by excluding it from the kit.
- Genuinely project-bound things stay put: a repo's schema, its business rules, its infrastructure names.
