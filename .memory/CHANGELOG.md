# CHANGELOG — ecosystem-kit

- 2026-07-29 — Headless launchers pass explicit --allowedTools (owner A/B = TRUST,
  not skip-permissions). Diagnosis: headless `claude -p` runs auto-mode
  unattended and blocks NETWORK git (fetch/push) + arbitrary code even in
  trusted folders with commands allowlisted — trust was necessary but not
  sufficient. Fix: weekly-hygiene/pr-comment-poller/pr-rebase now grant exactly
  their tools via --allowedTools (hygiene=local git only; poller/rebase=+safe-push
  +GitHub reply tools). Deny list (raw git push/config) + guard hooks still apply
  → far tighter than --dangerously-skip-permissions. Verified headless: network
  git fetch AND github MCP read both run under the grant.
- 2026-07-29 — guard_protected_merge now tracks `cd` and `git -C`, not just
  checkout/switch, when deciding the effective branch. Rebasing a FEATURE
  worktree onto main was wrongly blocked whenever the session's own repo sat
  on a protected branch (effective branch stayed the session repo's) — which
  also blocked the pr-rebase automation's own worktree flow. Now the branch
  actually being rewritten is evaluated; feature rebases pass, on-main
  rebases/merges/pushes still blocked. 10-case test incl. real worktree.
- 2026-07-29 — `tools/pr-rebase` + force-with-lease: a cron detects open PRs whose
  mergeable_state is 'dirty' (real base conflicts) and launches ONE headless
  session per new conflict to rebase onto base, resolve WITH understanding, run
  the gate, and (only if green) force-push-with-lease; aborts + comments
  otherwise. Never merges, never touches base. safe-push now allows
  --force-with-lease / --force-if-includes (bare --force/-f/--mirror/--delete
  still refused; protected-branch check runs first so lease-to-main is still
  refused). guard_dangerous_commands: bare force blocked, lease/if-includes
  allowed (negative-lookahead regex). `check` mode read-only.
- 2026-07-29 — bootstrap-machine.sh is now the kit-versioned home for the
  GitHub MCP tool grants the headless automation needs (read + reply/comment/
  create/update PR, both server variants; merge_pull_request still excluded/
  denied) — no more manual one-liner. Also: deploys all machine tools
  (adds kit-propagate, pr-rebase, unwedge-hooks; tolerant of missing ones),
  installs all four crons, and its manual steps skip-with-warning when run
  without a TTY instead of hot-looping.
- 2026-07-29 — Hook wiring made cwd-independent (fix/hook-cwd-wiring): settings.json.template commands now `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/_client.py" <hook>` (was bare-relative, which broke every hook when a session's persistent shell cwd drifted into a subdirectory); health-check accepts the new prefix (legacy relative still tolerated), docs/README/CLAUDE/CONVENTIONS + engine docstrings updated; obsoletes the rejected forwarding-shim workaround.
- 2026-07-29 — `tools/kit-propagate`: kit changes now flow to every registered
  repo as automatic update PRs (owner still merges). Daily cron; per repo:
  worktree off origin default → update.sh → policy patches (attribution off)
  → compile+import gate on every hook (repos with project-local engine
  additions fail safe with a logged skip, never a breaking PR) → safe-push →
  PR via GitHub API. Zero AI tokens. `check` mode is strictly read-only.
- 2026-07-29 — Two owner rules encoded at the source (feature/a11y-and-design): (1) accessibility compulsory — WCAG 2.1 AA a11y gate pattern in kit.config.example.{json,md} (G6, wired into standard/full/critical), Accessibility principle §9 in engineering-principles.md, MANDATORY a11y passes in reviewer.md + qa.md (N/A only with justification); (2) design direction lives in-repo — CONVENTIONS.md.template rule + /decide step 7: design decisions update .memory/references/design-direction* first, published claude.ai artifact is a regenerated mirror.
- 2026-07-24 — Knowledge cleanup (chore/knowledge-cleanup): adaptive-ceremony.md becomes the single home of the level→pipeline mapping (express drift resolved: express review = builder's own session, never a spawned task); DA scoring, autonomy rule, handoff checklist, and the "red tests, not prose" mantra de-duplicated into single owners with pointers; diary-template absorbed into /diary and deleted; machine layer documented (README + ARCHITECTURE §11); stale identifiers fixed (HOOK_MODULES→discover_hook_modules, GitHub MCP matcher wording, kit-update qualifier).
- 2026-07-24 — Machine layer versioned + bootstrap (owner: "would a fresh
  machine configure itself?" — it couldn't; now it can). `tools/` gains
  safe-push, weekly-hygiene, and guard_protected_branch.py (previously
  hand-built, unversioned in ~/.claude), plus `tools/bootstrap-machine.sh`:
  automated machine config (deploy tools to ~/.claude/bin + hooks-machine,
  merge guardrail permissions + branch-guard hook wiring into
  settings.local.json, install both cron entries, create dirs) followed by
  interactive manual steps (SSH key, PAT, Claude login, repo registration)
  each running a confirm→VERIFY→retry loop — a failed verification re-asks
  the same step with the failure reason. weekly-hygiene refactored off its
  hardcoded repo list onto the shared machine registry
  (~/.claude/repo-registry) — same review finding as the poller; both tools
  now read it, and the poller's register/unregister manages it. Tools
  auto-detect the claude binary (CLAUDE_BIN override supported).
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
