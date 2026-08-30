# DOCS-CHANGELOG — ecosystem-kit

- 2026-08-31 — STATE.md revalidated (busy week, reversing the last two: 13
  substantive commits landed 2026-08-27→08-30 after two quiet weeks; engine
  suite jumped 164→210, hook modules 12→13 (`artifact_sync`), wirings 16→17.
  Real corrections: (1) the stacked-unpushed-hygiene-commit backlog flagged
  2026-08-17/08-24 is cleared — `main` is 0 ahead/0 behind `origin/main`;
  (2) the `~/.claude/*` sandbox block that froze cross-repo claims across the
  prior four headless runs (ISSUES 2026-08-03) did NOT reproduce this run —
  `~/.claude/repo-registry`, every target's `.claude/kit-version`, and
  `crontab -l` all read successfully, surfacing a sixth registry line
  (`ecosystem-kit` itself, skipped by `kit-propagate` but not by
  `pr-comment-poller`/`pr-rebase`/`prune-stale-branches`) that STATE never
  recorded before because no prior run could see it. Flagged as one data
  point pending re-test, not a confirmed policy change (ISSUES). VERIFY's
  session_boot entry annotated with this new information; the two
  genuinely-mutating VERIFY items untouched (no new info, nothing changed).
  No other CHANGELOG-worthy change this run — all substantive work above was
  already logged as it landed.

- 2026-08-24 — STATE.md revalidated (third quiet week running: zero
  substantive commits since 2026-08-17, engine suite still 164/164, hook
  wiring still 12/16, unchanged). One real correction: the 2026-08-17 hygiene
  commit (`2dbf17a`) was never pushed — `main` sat 1 commit ahead of
  `origin/main` at this run's start, breaking the "no backlog" state noted
  last week; logged as ISSUES 2026-08-24 (this run adds a second unpushed
  commit on top, by design — hygiene runs never push). VERIFY.md's three open
  items re-annotated, still open, same reasons, no new info; sandbox boundary
  re-confirmed blocking `~/.claude/*` reads (4th consecutive headless run to
  hit it). No CHANGELOG-worthy change this run.

- 2026-08-17 — STATE.md revalidated (second quiet week running: zero
  substantive commits since 2026-08-10, engine suite still 164/164, hook
  wiring still 12/16, unchanged). One real correction: the previously-flagged
  unpushed hygiene commit is no longer unpushed — `HEAD` now matches
  `origin/main` (both `ae12eee` and `5766bd6` have landed on the remote since
  the last run). VERIFY.md's three open items re-annotated, still open, same
  reasons — re-confirmed the `~/.claude/*` sandbox boundary is unchanged
  (ISSUES 2026-08-03, re-tested this run). No CHANGELOG-worthy change this
  run.

- 2026-08-10 — STATE.md revalidated (quiet week: zero substantive commits
  since 2026-08-03, engine suite still 164/164, hook wiring still 12/16,
  only change is date restamp + a note that last week's hygiene commit is
  still unpushed by design). VERIFY.md's three open items re-annotated,
  still open, same reasons. No CHANGELOG-worthy change this run.

- 2026-07-29 — Owner rules a11y + design-direction. ADDED: `templates/memory/references/engineering-principles.md` §9 Accessibility (rule/smells/per-stack enforcement table) + Enforcement Map row; `kit.config.example.md` §"The a11y gate" (definition, ceremony wiring, per-stack command examples) + kit-wide convention bullet "Accessibility is compulsory"; example gate `G6 Accessibility` in `kit.config.example.json` wired into standard/full/critical; reviewer.md step 8 "Accessibility Review — MANDATORY" (hygiene renumbered to 9) + Accessibility line in Checklist Results + a11y gate added to gates-owned; qa.md step 5 "Accessibility Verification — MANDATORY" (mutation renumbered to 6) + Accessibility Results table + checklist item + risk-priority placement; CONVENTIONS.md.template rules "Accessibility is compulsory" and "Design direction lives in-repo"; `templates/commands/decide.md` step 7 (design decisions → update design-direction doc first, republish artifact second).

- 2026-07-24 — Knowledge cleanup. MOVED: level→pipeline table now lives only in `templates/skills/adaptive-ceremony.md` (conductor Phase 3 + handoff pipelines → pointers); DA scoring tables only in `templates/skills/devils-advocate.md` (reviewer → pointer); autonomy rule + handoff checklist single-homed in `templates/memory/references/team-member-protocol.md` §Autonomous Mode / `templates/skills/handoff.md` (architect + protocol restatements dropped); "red tests" escalation+watermark only in `templates/memory/references/engineering-principles.md` (decide/retro/CONVENTIONS/DECISIONS/CLAUDE.md.template → clause+pointer); diary skeleton moved into `templates/commands/diary.md`. DIED: `templates/memory/diary-template.md` (never installed by install.sh; content absorbed into /diary), adaptive-ceremony §Branch Naming (ops.md owns it). ADDED: README machine-layer paragraph + `tools/` layout row; ARCHITECTURE §11 Machine layer + §10 `_note`-is-SSOT note.

- 2026-07-23 — Seeded the kit's own `.memory/` roster (STATE, DECISIONS, ISSUES, IDEAS, GOTCHAS, CONVENTIONS, VERIFY, CHANGELOG, DOCS-CHANGELOG) with the founding decisions, conventions, and open verification items of kit v1.0.0.
