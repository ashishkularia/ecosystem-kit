# Adaptive Ceremony

## Purpose

Not every change deserves the same level of process. This skill defines how ceremony level
is classified, how auto-escalation triggers are detected, and how the SDLC pipeline depth
is adjusted to match the risk and scope of each change.

## Ceremony Levels

The kit defines four ceremony levels. **Which quality gates each level enforces is defined
in `.claude/kit.json` `ceremony.levels` — resolve it there, never from this file.** The
project default is `kit.json` `ceremony.default`.

**This table is the single home of the level → pipeline mapping.** The conductor's task
plan and the handoff transitions both resolve from it — no other doc restates it:

| Level | Pipeline | When |
|-------|----------|------|
| express | conductor → builder → done | Typos, copy, config tweaks, docs, single-file fixes with existing test coverage |
| standard | conductor → architect → builder → reviewer → done | Bug fixes, small features, CRUD modules, new endpoints |
| full | conductor → architect → builder → reviewer + qa (parallel) → done | Major features, multi-domain changes, complex flows |
| critical | conductor → architect → builder → reviewer + qa (parallel) → ops → done (human gates between phases) | Auth, payments/billing, data migrations, security-sensitive paths, anything where a mistake is expensive to reverse |

**Express review**: the builder performs a lightweight review of its own work inside its
own session — an express pipeline never spawns a review task or review agent.

**Ops below critical**: only the critical pipeline includes the ops agent. At every other
level the builder performs the ops checklist itself (commit hygiene, `.memory/CHANGELOG.md`
entry, branch rules — see `ops.md` for the checklist).

If `merge_is_deploy` is true in `kit.json`, treat everything that will land on a protected
branch with one extra notch of suspicion — a merge is a production deploy.

## Classification Algorithm

### Step 1: Keyword Scan

| Signal in the request | Base level |
|-----------------------|-----------|
| "typo", "copy", "wording", "docs", "config tweak" | express |
| "fix", "add field", "update endpoint", "refactor", "rename", "new feature", "CRUD" | standard |
| "multi-domain", "major feature", "workflow", "integration" | full |
| "auth", "login", "billing", "payment", "migration", "security", "permission", "role" | critical |

### Step 2: Scope Scan

Use Glob/Grep to estimate the affected files:

| File count | Suggested level |
|-----------|-----------------|
| 1-3 | express |
| 4-15 | standard |
| 16-25 | full |
| 26+ or critical-path files | critical |

### Step 3: Base Level

`base_level = max(keyword_level, scope_level)`

### Step 4: Auto-Escalation Check

Auto-escalation can only raise the level, never lower it. Escalate to **critical** when the
change touches:

- Authentication, session, or token logic
- Payment, billing, or subscription logic
- Authorization decisions (policies, roles, permissions, middleware)
- Schema/data migrations (data integrity)
- Isolation of per-user / per-tenant data (leak risk)
- Anything the project profile or `.memory/CONVENTIONS.md` names as a critical path

Escalate to at least **full** when the change touches PII handling or crosses domain
boundaries. Projects record additional domain-specific escalation rules in
`.memory/CONVENTIONS.md` — check it during classification.

### Step 5: Present Classification

```markdown
## Ceremony Classification
**Request**: <summary>
**Keyword signal**: standard — "add endpoint"
**Scope signal**: standard — 12 files
**Auto-escalation**: critical — touches migrations
**Final level**: critical
Gates: <resolved from kit.json ceremony.levels.critical>
Would you like to adjust? (express / standard / full / critical)
```

## Downgrade / Upgrade Rules

**Downgrade** only when ALL of: the user explicitly requests it, no auto-escalation trigger
is present, and no critical-path files are affected. The level can never go below the
auto-escalation floor.

**Upgrade** any time. Common reasons: discovery reveals more files than estimated,
cross-domain dependencies surface during architecture, security implications appear during
review, the builder hits unexpected complexity.

## Hotfix Mode

For production-critical fixes that cannot wait for full ceremony:

1. Classify as **standard** regardless of scope
2. Apply critical-path safeguards anyway: a targeted test for the specific fix, manual
   verification that auth/data isolation is intact, a documented rollback plan
3. Branch: `hotfix/<description>` (if `hotfix` is in `branch_types`, else the closest fix type)
4. Post-merge: record a follow-up in `.memory/ISSUES.md` for review at proper ceremony

## Quick Decision Matrix

```
Touches auth, payments, migrations, permissions, or per-user data isolation?
  YES → critical
Spans multiple domains or needs end-to-end verification?
  YES → full
Trivial (typo/copy/config/docs, covered by existing tests)?
  YES → express
Everything else → standard
```

## Related Skills

- `discovery.md` — discovery results (affected files, domain signals) feed classification
- `planning.md` — ceremony level determines planning depth and required artifacts
- `handoff.md` — ceremony level determines which agents participate
- `self-check.md` — validates that the chosen level is still correct as work progresses
