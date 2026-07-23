# VERIFY — ecosystem-kit — open acceptance checks

Format: `- [ ] item — how to verify`

- [x] install.sh end-to-end against the REAL engine+templates — verified 2026-07-23 against scratch git repos with ALL FIVE profiles: full `.claude/` (15 hook modules, 10 commands, 6 agents, 7 skills) + `.memory/` layout, tests/ not installed, re-run a no-op (0 seeded / 9 untouched, 0 gitignore lines re-appended), edited `.memory/STATE.md` and tuned `kit.json` byte-identical after re-run. Error paths verified: non-git dir refused, kit-into-itself refused, unknown profile lists available ones.
- [x] update.sh refreshes engine+skills only — verified 2026-07-23 against the real kit: drifted hook + skill refreshed, project-customized command and `.memory/`/`kit.json` byte-identical, non-kit hook left in place with a NOTE, changed files listed (0 new, 2 updated, 20 unchanged).
- [x] health-check.sh on a fresh real install — verified 2026-07-23: wiring parity OK, roster complete, drift detection fires (unwired module named, exit 1). Only ERR on this machine is the true-positive `~/.claude/settings.local.json` leak (see ISSUES).
- [ ] session_boot additionalContext appears at session start in a real project (mylantite first) — restart session, confirm STATE head + VERIFY/ISSUES counts + diary tail + always_load instruction in context.
- [ ] docs_contract Stop-gate blocks until CHANGELOG/diary updated and honors stop_hook_active — edit a source-pattern file, try to stop, confirm block then release.
- [ ] guard_protected_merge blocks: `git merge` into main, `gh pr merge`, `git push` refspec targeting main, github MCP write tools on protected branches.
- [x] Engine unittest suite passes on host: `python3 -m unittest discover engine/hooks/tests` — 90 tests OK, verified 2026-07-23.
- [ ] Fail-open/fail-closed split behaves: break an advisory hook, confirm tools still run with a stderr warning; break `secret_scanner`, confirm Edit/Write blocked (exit 2).
