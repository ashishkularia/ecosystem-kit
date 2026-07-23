# Handoff

## Purpose

Agents in the SDLC pipeline must transfer context cleanly between phases. Without
structured handoffs, the next agent wastes cycles re-discovering what the previous agent
already knew. This skill defines what each agent passes to the next, the message format,
and how errors are escalated.

For the full team member lifecycle and shutdown procedures, see
`.memory/references/team-member-protocol.md`.

## Ceremony-Specific Pipelines

The ceremony level (`.claude/kit.json` `ceremony`) defines which agents are in the
pipeline and thus which handoff transitions occur:

| Level | Pipeline |
|-------|----------|
| express | conductor → builder → done |
| standard | conductor → architect → builder → reviewer → done |
| full | conductor → architect → builder → reviewer + qa (parallel) → done |
| critical | conductor → architect → builder → reviewer + qa (parallel) → ops → done (human gates between phases) |

## Handoff Content by Transition

| From | To | Content |
|------|----|---------|
| Conductor | Architect | Requirements, ceremony level, acceptance criteria |
| Architect | Builder(s) | Architecture doc, file manifest, interface contracts |
| Builder | Builder (peer) | Interface contracts (routes, shapes, names) as soon as stable |
| Builder(s) | Reviewer / QA | Changed-files list, test results summary, assumptions made |
| Reviewer | QA | Review verdict, findings, concerns to probe |
| Reviewer / QA | Conductor | Final verdict with DA findings and risk score |
| Conductor | Ops | Gate results, changed files, changelog material |

## Handoff Message Template

Every handoff follows this structure — adapt sections to the role; not every section
applies to every transition:

```markdown
## <Agent Name> — Completion Report

### Summary
<1-2 sentences: what was done, what's the outcome>

### Files Changed
| Action | File |
|--------|------|
| CREATE | <path> |
| MODIFY | <path> |

### Test Results
- Suite: N tests, N failures (command per kit.json quality_commands.test)
- New tests added: N

### Concerns / Risks
- <issues discovered; things the next agent should watch>

### Notes for Next Phase
- <specific guidance for the next agent>

### Memory Flags
- <entries to append to .memory/ — DECISIONS, GOTCHAS, ISSUES, VERIFY>

### Devil's Advocate Summary
<required — see devils-advocate.md for format; conductor rejects reports without it>
```

## Handoff Checklist

Before sending a completion report, every agent verifies:

1. All assigned tasks completed (or documented why not)
2. Task status updated
3. Files created/modified listed
4. Test results included (pass count, failure count)
5. Blockers and risks noted
6. Next-agent guidance included
7. Memory flags included (what should outlive this session)
8. DA summary present

## Error Handoff

When an agent hits a failure it cannot resolve:

```yaml
error_handoff:
  from: builder
  error_type: test_infrastructure_failure
  message: "<what is broken>"
  attempted_fixes:
    - "<what was tried>"
  recommendation: "<who should look at what>"
  retry_count: 2
  max_retries: 3
```

## Conductor Decision Tree (on failure)

| Strike | Action |
|--------|--------|
| 1 | Retry with additional error context |
| 2 | Reduce scope or offer override |
| 3 | Abort agent, report failure to user |

## Related Files

- `.memory/references/team-member-protocol.md` — full lifecycle protocol
- `.claude/skills/devils-advocate.md` — DA findings format for completion reports
- `.claude/skills/adaptive-ceremony.md` — pipeline definitions per ceremony level
