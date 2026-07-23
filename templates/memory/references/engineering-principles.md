# Engineering Principles

The principles every agent in this ecosystem builds and reviews against. For each: the
rule, the smells that betray a violation, and **how it is enforced here** — because a
principle without an enforcement mechanism is a wish.

Per-principle rigor is configured in `.claude/kit.json` `principles`
(`enforce` / `advise` / `off`). The hooks referenced below live in `.claude/hooks/`.

**The enforcement escalation path**: prose convention → advisory hook → blocking hook or
architecture test. When the owner states an always/never rule, encode it as a red test in
the same session — with a shrink-only baseline (watermark) if violations already exist so
the count can only ever go down. Prose conventions don't survive sessions; red tests do.

---

## 1. DRY — Don't Repeat Yourself

**Rule**: Every piece of knowledge has one authoritative representation. Duplicate the
*call*, never the *logic*. But: a little duplication is cheaper than the wrong
abstraction — extract on the third occurrence, not the first.

**Smells**:
- The same validation/calculation copy-pasted into two handlers, already drifting apart
- A constant (URL, limit, enum value) hardcoded in three files
- Parallel test setups that differ only in one field, rebuilt from scratch each time

**Enforced by**: `guard_principles` hook (`dry_kiss` — advisory guidance on
Edit/Write); reviewer convention-compliance pass. For structural duplication rules
("all X go through Y"), copy the architecture-test pattern: a test that greps the source
tree and fails on new violations against a shrink-only baseline.

## 2. KISS — Keep It Simple

**Rule**: The simplest design that satisfies the requirement wins. Complexity must be
purchased by a real, present need — not a speculative future one (YAGNI).

**Smells**:
- An interface + factory + strategy for a thing with exactly one implementation
- Configuration options nobody asked for ("just in case")
- Abstraction layers that only forward calls to the next layer down

**Enforced by**: `guard_principles` hook (`dry_kiss` advisory); Devil's Advocate
architecture dimension (`da-checklist.md` — over-engineering check); architect's design
checklist ("simplest design that satisfies the requirement").

## 3. TDD — Test-Driven Development

**Rule**: Red-Green-Refactor. Write a failing test, write the minimum code to pass,
refactor with tests green. Every behavior earns its existence by a test that fails
without it.

**Smells**:
- A source file edited all session with zero matching test edits
- Tests written after the fact that mirror the implementation (they can never fail)
- "I'll add tests in a follow-up PR" (the follow-up never comes)

**Enforced by**: `tdd_gate` hook — advisory reminder when source (per `kit.json`
`source_patterns`) is edited without test edits; **exit-2 blocking** when
`principles.tdd` is `enforce`. Backed by the test gate in `kit.json` `gates` and the
builder's cycle log in every completion report.

## 4. WYSIWYG — Honest UI and Honest Code

**Rule**: What you see is what it does. A button that says "Save" saves — it doesn't
also silently delete drafts. A function named `getUser` gets a user — it doesn't also
mutate state. UI never shows controls that don't work, data that isn't real, or success
states that aren't verified.

**Smells**:
- Placeholder/mock data left rendering in a real screen
- A function whose name promises a query but performs a write
- Disabled features shown as enabled; optimistic "Saved!" with no error path
- Demo hardcodes ("always returns true for now") surviving past the demo

**Enforced by**: reviewer contract-validation and hygiene passes; QA's "expected vs
actual" verification of acceptance criteria. For recurring dishonesty patterns, add an
architecture test (e.g., grep-fail on `TODO: fake`, `hardcoded`, mock imports outside
test paths).

## 5. Fail Fast

**Rule**: Detect problems at the earliest possible moment and stop loudly. Validate at
boundaries, throw on impossible states, never swallow an error you can't handle
meaningfully.

**Smells**:
- Bare `except:` / empty `catch {}` blocks that swallow exceptions silently
- Returning `null`/default on error so the failure surfaces three layers later
- Accepting invalid input and "fixing it up" instead of rejecting it

**Enforced by**: `guard_principles` hook (`fail_fast` — flags bare-except/empty-catch on
Edit/Write); DA reliability dimension (error-handling gaps); ORM/runtime strict modes
(e.g., forbidding lazy loading or silently discarded writes) where the stack supports
them — the runtime layer of the same idea.

## 6. Structured Logging

**Rule**: Use the project's logger with context (actor, action, identifiers) — never
print-debugging in production source. Log at the right level; security-relevant events
always carry actor attribution.

**Smells**:
- `print()` / `console.log()` / `var_dump()` in non-test source when a logger exists
- Log messages without identifiers ("update failed" — whose? which?)
- Sensitive values (tokens, passwords, PII) written to logs

**Enforced by**: `guard_principles` hook (`logging` — flags print-style calls in non-test
source when a logger exists); `secret_scanner` hook for sensitive values; reviewer hygiene
pass; DA security dimension (audit-logging check).

## 7. Dead Code Removal

**Rule**: Delete unused code — don't comment it out, don't keep it "just in case".
Version control is the archive; the working tree is for code that runs.

**Smells**:
- Large commented-out blocks ("might need this later")
- Feature-flagged paths whose flag can never be true anymore
- Unreferenced files, exports nothing imports, functions nothing calls

**Enforced by**: `guard_principles` hook (`dead_code` — flags large commented-out blocks
on Edit/Write); reviewer hygiene check (no commented-out code, no dead files);
`docs_contract` keeps `.memory/CHANGELOG.md` honest about what actually changed.

## 8. Clean, Readable Code

**Rule**: Code is read far more often than written. Names say what things are; functions
do one thing; nesting stays shallow; formatting is the machine's job, not a debate.

**Smells**:
- Functions that need a scroll bar; parameter lists that need a paragraph
- Names like `data2`, `handleStuff`, `tmp` in committed code
- Style drift that the formatter would have fixed if anyone had run it

**Enforced by**: `kit.json` `quality_commands.format` / `.lint` / `.typecheck` — run by
builder every cycle, verified by reviewer, gated before commit by ops;
`guard_commit_message` keeps history readable too (Conventional Commits, advisory).

---

## Enforcement Map (quick reference)

| Principle | Hook | Blocking? | Backstop |
|-----------|------|-----------|----------|
| DRY | `guard_principles` (dry_kiss) | advisory | reviewer + architecture-test pattern |
| KISS | `guard_principles` (dry_kiss) | advisory | DA architecture dimension |
| TDD | `tdd_gate` | blocking when `principles.tdd=enforce` | test gate per kit.json |
| WYSIWYG | — (review-enforced) | no | reviewer + QA acceptance verification |
| Fail fast | `guard_principles` (fail_fast) | advisory | DA reliability dimension |
| Structured logging | `guard_principles` (logging) | advisory | `secret_scanner` (blocking) |
| Dead code | `guard_principles` (dead_code) | advisory | reviewer hygiene check |
| Clean code | — | via quality gates | `quality_commands` in every gate |
