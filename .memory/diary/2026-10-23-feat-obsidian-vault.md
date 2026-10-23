# feat/obsidian-vault

## Session — 2026-10-23

- **Context:** the owner wants ideas, conventions, memories, changelogs and docs in
  Obsidian, one vault with a folder per project, so they and Gunjan can read and edit
  them on the go. The vault already existed (`~/Notes/Kularia`, Self-hosted LiveSync,
  end-to-end encrypted, `ashish` and `gunjan` logins, both see everything). The owner
  confirmed Gunjan should see all repo data and reminded me that Obsidian ignores
  dot-folders.
- **Decided:** git stays the source of truth for anything the machinery reads; the
  vault gets a one-way copy and an Inbox. Auto memory moves to the vault outright.
  Scratch, `.memory/cache/` and secrets never sync. IDEAS.md stays in git for now:
  it is wired into the installer roster, health-check, `/idea`, `/summary` and
  weekly-hygiene, so moving it is a separate change.
- **Built:** `tools/vault-sync` (mirror, `check`, `adopt-memory`), the session_boot
  vault section, the `vault` CLAUDE.md block, bootstrap wiring and hourly cron.
- **Verified:** 15 new tests; full suite 306 OK. Before the first real run I scanned
  the 491 files to be copied for credential patterns and found none. The first run
  wrote 491 files across 7 repos, and a second run wrote 0.
- **Changed after review:** the owner postponed the memory move because other
  sessions are running, and wants the repos moved one at a time. `adopt-memory`
  now takes a repo directory name (or `all`) and refuses to run without one.
- **Open:** `adopt-memory` was refused by the permission classifier (it rewrites
  settings.local.json in seven repos and copies notes to a synced location), so the
  owner runs it. After that, DevContainer, mylantite and meritick each need a PR that
  stops tracking `.memory/auto/` (4, 51 and 3 notes). PR #52 edits the same bootstrap
  line, so whichever merges second needs a one-line rebase.
