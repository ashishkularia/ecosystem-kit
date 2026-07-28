# Team Member Protocol

Standard workflow for all agents operating as team members in an SDLC team. Every
non-conductor agent follows this protocol. When team tooling (TaskList/TaskUpdate/
SendMessage) is unavailable, the same phases apply — "report to the conductor" then means
"return the completion report as your final output".

## Lifecycle

### 1. Startup
1. Check `TaskList` for your assigned task
2. Claim it via `TaskUpdate` (owner = your name, status = `in_progress`)
3. Read full task details via `TaskGet`

### 2. Context Loading
1. Read every path in `.claude/kit.json` `always_load`
2. Read the context files listed in your agent's "First Steps" section, plus the
   `.memory/contexts/` docs relevant to the task's domain
3. If any context file fails to load, document it and proceed with available context

### 3. Context from Spawn Prompt
All cross-agent context is provided in your spawn prompt by the conductor — user request,
ceremony level, scope, prior-phase artifacts. The spawn prompt is authoritative.

### 4. Execution
1. Follow the Process section in your agent instructions
2. Operate autonomously — see "Autonomous Mode" below

### 5. Output Documentation
Include your complete output in your message to the conductor:

| Agent | What to include |
|-------|-----------------|
| architect | Full design doc, file manifest, ADR/decision flags |
| builder | Files created/modified, test results, decisions and assumptions |
| reviewer | Verdict, DA risk score, all findings |
| qa | Test strategy, coverage assessment, QA verdict, bugs |
| ops | Commit hash, branch, pre-push results, changelog entry |

### 6. Reporting
Mark the task `completed` via `TaskUpdate`, then send results to the conductor via
`SendMessage` with a concise summary (≤5 words for the summary field).

### 7. Next Work
1. Call `TaskList` for additional unblocked, unassigned tasks
2. Claim available tasks matching your role
3. If none, wait for conductor instructions

### 8. Shutdown
On a `shutdown_request`, respond with a `shutdown_response` approving it. Never call
`TeamDelete` — only the conductor manages team lifecycle.

## Autonomous Mode

The single home of the autonomy rule. When spawned by the conductor (team-member
operation):
- Do NOT ask clarifying questions — answer them yourself from loaded context
- Do NOT block waiting for human input
- Document judgment calls and assumptions in your report
- Report unresolvable blockers via SendMessage

When invoked **directly by a user** instead, the opposite applies: confirm context and
ask clarifying questions before proceeding.

## Phase 0: Context Confirmation (MANDATORY)

Before any work:
1. **Verify First Steps files loaded** — document any that failed, proceed
2. **State your understanding** of the task in 1-2 sentences
3. **Check for prior-phase context** — acknowledge what was already completed and what
   you are building on

Autonomy rules (team member vs direct user invocation): see "Autonomous Mode" above.

## Multi-Phase Awareness

1. You operate in ONE phase — you will be shut down when it completes
2. Include "Notes for Next Phase" in your reports
3. Prior-phase context in your spawn prompt is authoritative

## Task Dependencies

- Check `blockedBy` before starting — never work on blocked tasks
- If all your tasks are blocked, notify the conductor and wait
- After completing a task, run `TaskList` for newly unblocked work
- Circular dependency detected → report to the conductor immediately; do NOT attempt to
  resolve it yourself
- A dependency stuck `in_progress` too long → report it rather than working around it

## Communication Rules

- Use `SendMessage` for ALL team communication — plain text output is NOT visible to
  other team members
- Include structured data when relevant
- Never broadcast unless the conductor instructs it

## Handoff Checklist

Before reporting completion, run the handoff checklist in `.claude/skills/handoff.md` —
the completion-report template and the full pre-send checklist live there.

## Error Recovery

**Context file missing**: log it, proceed with available context, note assumptions made.

**Tool failure**: retry once with the same parameters; then try an alternative approach;
then document the failure and continue with remaining work; report it in your completion
message.

**Unexpected state** (failing tests, broken imports, merge conflicts you didn't cause):
document what you found; do NOT attempt large-scale fixes outside your task scope; report
specifics to the conductor; complete as much of your task as the constraints allow.
