# IDEAS — ecosystem-kit

Format: `- [ ] YYYY-MM-DD — idea`

- [x] DONE (2026-07-23) — Placeholder substitution in templates (`{{PROJECT}}`, `{{STACK}}`) — implemented in install.sh (`render_file`: PROJECT/STACK/DATE/REPO_ABS) for the `.memory/` roster and CLAUDE.md. Agent/command/skill templates carry no placeholders, so they stay verbatim copies on purpose.
- [ ] 2026-07-23 — `health-check.sh --fix` mode for mechanical repairs: missing `.gitkeep`s, missing `cache/.gitignore`, stale kit-version stamp.
- [ ] 2026-07-23 — Per-project extra hooks dir (`.claude/hooks-local/`) globbed by the daemon but never touched by `update.sh`, so projects can add hooks without forking the engine.
- [ ] 2026-07-23 — `install.sh --dry-run` that prints the full action plan without writing anything.
- [ ] 2026-07-23 — Kit CI: run `python3 -m unittest discover engine/hooks/tests` + a fixture install/update/health-check round-trip on every kit PR (the same harness used during authoring).
