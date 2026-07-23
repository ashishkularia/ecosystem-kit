# Devil's Advocate (DA)

## Purpose

The Devil's Advocate protocol ensures every agent actively looks for flaws, risks, and
oversights. This skill defines when DA checks trigger, how findings are recorded and
scored, and how they flow through the pipeline.

## Philosophy

The DA is not a separate agent. It is a **mindset** applied at critical transition points.
Each agent asks: "What could go wrong? What did I miss? What assumption might be wrong?"

Agents naturally focus on "did I build what was asked?" and skip "what could go wrong?"
Without a forcing function, risk review doesn't happen consistently — that is why the DA
summary is mandatory in every completion report.

## Canonical Checklist

The consolidated DA checklist lives at `.memory/references/da-checklist.md` and covers
four dimensions: **architecture, security, performance, reliability**. It is the single
source of truth — this skill defines process, the checklist defines the checks.

## DA Scope by Ceremony

| Ceremony (per kit.json) | DA scope |
|--------------------------|----------|
| express | Quick pass: security + reliability questions only, advisory |
| standard | Architecture + reliability dimensions (advisory), security always blocking |
| full | All 4 dimensions with full rigor |
| critical | All 4 dimensions + human review of findings |

## How to Execute

1. Read `.memory/references/da-checklist.md`
2. Evaluate each check in the dimensions assigned to your ceremony level against the work under review
3. Assign each finding a severity (Critical / High / Medium / Low)
4. Record findings in the YAML format below
5. Score using the severity weights
6. Include the findings in your completion report (see `handoff.md`)

## DA Transition Points

| Transition | Key questions |
|-----------|--------------|
| Architect → Builder | Ceremony level correct? Scope proportional? Alternatives considered? |
| Builder → Reviewers | All acceptance criteria addressed? Concerns flagged? Assumptions documented? |
| Reviewer → Conductor | Findings match scope? Severity ratings calibrated, not inflated or soft? |
| Workflow end (Conductor) | Original problem solved? Unresolved concerns documented in `.memory/ISSUES.md`? |

## Risk Scoring

Numeric scoring makes risk thresholds objective. A single Critical finding (e.g., a
cross-user data leak) outweighs several Medium findings (e.g., a missing index) because
the blast radius is fundamentally different.

### Severity Weights

| Severity | Points | Calibration |
|----------|--------|-------------|
| Critical | 10 | Data leak, auth bypass, data-loss risk, secret exposure |
| High | 5 | Missing authorization check, unhandled edge case in money/state logic |
| Medium | 2 | Missing index, suboptimal query, missing error handling on a non-critical path |
| Low | 1 | Style issue, minor optimization opportunity |

### Risk Thresholds

| Score | Status | Action |
|-------|--------|--------|
| 0-5 | GREEN | Proceed |
| 6-15 | YELLOW | Proceed with documented risks |
| 16+ | RED | Must address before proceeding |
| Any Critical | AUTO-BLOCK | Cannot proceed until resolved |

## Findings Format

```yaml
da_findings:
  architecture:
    verdict: PASS|PASS_WITH_NOTES|FAIL
    score: N
    findings:
      - check: "<check name from da-checklist.md>"
        severity: Medium
        description: "<what was found>"
        recommendation: "<fix or accepted-risk rationale>"
  security:
    verdict: PASS
    score: 0
  performance:
    verdict: PASS
    score: 0
  reliability:
    verdict: PASS_WITH_NOTES
    score: 3
    findings: [...]
  total_score: N
  overall_verdict: PASS|PASS_WITH_NOTES|FAIL
```

## Enforcement Rules

1. Every completion report includes a "Devil's Advocate Summary" section
2. If missing, the conductor returns the report for resubmission
3. The conductor validates DA summaries at each transition point
4. Critical findings block the pipeline until resolved
5. High findings should be addressed before the review gate passes
6. Accepted risks (YELLOW proceeds) are recorded in `.memory/ISSUES.md` so they don't
   silently evaporate at session end

## Related Files

- `.memory/references/da-checklist.md` — the consolidated four-dimension checklist
- `.claude/skills/handoff.md` — completion report template that carries DA findings
- `.claude/skills/self-check.md` — the non-adversarial counterpart
