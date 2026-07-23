# CONVENTIONS — ecosystem-kit

- Python: stdlib ONLY, `python3`, no pip/venv. Tests use `unittest` (pytest may not exist on hosts). Hooks live flat in `engine/hooks/`; `_`-prefixed files are infrastructure, everything else is a dispatchable hook module.
- Shell: bash with `set -euo pipefail` (`health-check.sh` deliberately drops `-e` — its checks are expected to fail without aborting the run). `shopt -s nullglob` before glob loops.
- JSON in shell: always python3 heredocs/one-liners, never jq (not installed on hosts).
- Hook wiring: relative commands only — `python3 .claude/hooks/_client.py <hook>` — and ONLY in `.claude/settings.json`. No hooks blocks in settings.local.json or user-level settings.
- Install semantics: copy, never symlink. Engine overwrite is OK (kit-owned); knowledge (`.memory/`, `kit.json`, existing `settings.json`, `CLAUDE.md`) is never clobbered.
- Dates: ISO `YYYY-MM-DD` everywhere — DECISIONS entries, diary filenames, changelogs.
- No secrets in any kit file or installed file, ever.
- Protected branches: Claude never merges/pushes to main/master; the owner merges.
- `.memory/cache/` is runtime scratch: self-gitignored via a TRACKED `.gitignore` containing `*` + `!.gitignore` (so the dir survives clones; no root-level `.memory/cache/` ignore line — that would untrack the mechanism itself), recreated by installer/hooks, never carries knowledge.
- Memory-roster templates and CLAUDE.md are RENDERED at install (`{{PROJECT}}`/`{{STACK}}`/`{{DATE}}`/`{{REPO_ABS}}` via install.sh `render_file`); command/agent/skill templates carry no placeholders and are copied verbatim by design. Project customization happens after install in the target repo.
