# Self-Check

## Purpose

Self-checks catch drift before it compounds. A builder that builds three files in the
wrong direction wastes three TDD cycles. A conductor that spawns reviewers for the wrong
ceremony level wastes entire agent budgets. Self-checks are cheap insurance — a few
questions at transition points that prevent expensive rework.

## When to Self-Check

| Trigger | Who | Key question |
|---------|-----|-------------|
| Before spawning an agent | Conductor | Is the ceremony level still correct? |
| After an agent completes | Conductor | Did the required gates (per kit.json) pass? |
| Before writing code | Builder | Am I aligned with the architecture and manifest? |
| After each TDD cycle | Builder | Do tests pass? Any drift from the plan? |
| Before sending a verdict | Reviewer | Did I check all categories fairly? |
| Before sending a report | QA / Ops | Did I verify the domain-specific risks? |
| Before ending the session | Everyone | Is the knowledge trail written to `.memory/`? |

## Conductor Self-Checks

**Ceremony level** — before every spawn, verify new information hasn't invalidated the
classification. Scope growth, newly discovered files, or domain signals may trigger
auto-escalation (see `adaptive-ceremony.md`).

**Spawn budget** — if remaining budget is tight: combine review tasks (reviewer absorbs QA
checks), skip optional agents when their domain is untouched. Builders are never skippable.

**Quality gates** — after each agent completes, verify the relevant gates passed. Gate
definitions and commands come from `.claude/kit.json` `gates`.

**Loop detection** — am I re-spawning the same agent with the same input, cycling
review-fix past 3 rounds, or getting identical output twice? Thresholds and actions:
`conductor.md` "Circuit Breaker".

## Builder Self-Check

**TDD discipline** (rigor per `kit.json` `principles.tdd`):
- Test written before production code
- Test fails for the expected reason (not a test bug)
- Minimum code to pass, then refactor without behavior change

**Architecture alignment**:
- File placement matches the manifest
- Interfaces match the architecture document
- No unplanned files creeping in

**Project conventions**:
- Everything in `.memory/CONVENTIONS.md` honored
- Comparable existing code mirrored, not reinvented

**Coverage**:
- Each new public behavior has a test
- Authorization tested in both directions where applicable
- Edge cases: empty, null, boundary values

## Reviewer Self-Check

**All categories reviewed**: conventions, static analysis (all `kit.json`
`quality_commands`), security, performance, test coverage, hygiene.

**Fairness**:
- Critical findings are genuinely blocking, not style preferences
- Suggested fixes are actionable, not vague
- Positive observations included alongside negatives

**Verdict consistency** — does my verdict follow mechanically from my findings?
(Mapping: `reviewer.md` "Fairness Rules".)

## QA Self-Check

- Cross-user/tenant access denied in both directions (where multi-user data exists)
- Lists/search scoped to the caller
- Each role tested for each action, including the denial cases
- Critical paths identified and covered; coverage gaps named, not hand-waved

## Ops Self-Check

- All `quality_commands` green before commit
- Conventional Commit format; specific files staged; no secrets
- Branch type from `kit.json` `branch_types`; protected branches untouched
- `.memory/CHANGELOG.md` entry written; this change's diary entry appended to
  if `kit.json` `diary` (any decision or discussion must already be in it — the
  pre-commit gate blocks otherwise)
- Push presented as a human gate; merge left to the owner

## When a Self-Check Fails

1. **Ceremony mismatch** → escalate immediately to the conductor
2. **Quality gate failure** → document what failed and what needs to change
3. **Architecture drift** → stop, notify conductor, wait for revised design
4. **Budget exhaustion** → combine tasks or skip optional agents
5. **Domain risk discovered** → escalate ceremony level

## Related Skills

- `adaptive-ceremony.md` — classification and auto-escalation rules
- `handoff.md` — self-check runs before every handoff
- `devils-advocate.md` — DA checks are the adversarial cousin of the self-check
