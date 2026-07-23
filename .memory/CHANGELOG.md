# CHANGELOG — ecosystem-kit

- 2026-07-24 — `tools/pr-comment-poller`: cron-driven GitHub poller closing the
  "owner comments on a PR, nobody notices until a session opens" gap. Pure API
  polling (no AI cost) until new owner comments appear on an open PR, then one
  headless `claude -p` run in that repo addresses them (worktree for code,
  safe-push, signed replies via trailing marker for loop safety, never merges).
  Credential comes ONLY from owner-provisioned `~/.secrets/github-pat` — the
  tool never scrapes tokens from any config.
- 2026-07-23 — Verification fix pass (16 verifier findings): daemon cooldown file renamed `.daemon.start_attempt` so the `.daemon.*` gitignore glob covers it; installed `.memory/` layout now survives a git round-trip (tracked `cache/.gitignore` = `*`+`!.gitignore`, root `.memory/cache/` snippet line removed + scrubbed on re-install, `.gitkeep` seeded into empty `diary/`/`auto/`); WHERE-less DELETE check mirrors the UPDATE rule (quoted `mysql -e "DELETE FROM x"` now blocked); filesystem/git guard patterns ignore quoted text (commit messages mentioning `rm -rf` no longer block); docs_contract + tdd_gate skip out-of-repo files; conductor delegates write-phases instead of "running them itself"; `/decide`+`/idea` drop docs_contract flags; `file_write_rules` added to schema defaults/example/doc; README/ARCHITECTURE/kit.config.example.md drift corrected. Verified: engine suite 94/94, fresh meritick install + clone round-trip 0 ERR, 8/8 behavioral hook checks.
- 2026-07-23 — install.sh now renders `{{PROJECT}}`/`{{STACK}}`/`{{DATE}}`/`{{REPO_ABS}}` when seeding the `.memory/` roster and CLAUDE.md (was verbatim copy — seeded STATE.md carried a literal `{{DATE}}`, so session_boot's staleness regex could never match); gitignore.snippet gains `.claude/hooks/__pycache__/` (daemon imports write bytecode into target repos); ISSUES/VERIFY template format-examples re-quoted mid-line so session_boot's `- [ ]` counter reads 0, not 1, on a fresh install. Verified by a scratch-repo install: render, idempotent re-run, live session_boot, health-check 17 OK.
- 2026-07-23 — kit v1.0.0 authored
- 2026-07-23 — installer/updater/health-check verified end-to-end against the real engine+templates for all five profiles (install, re-run idempotency, update scope, drift detection, error paths); engine suite 90/90 green
