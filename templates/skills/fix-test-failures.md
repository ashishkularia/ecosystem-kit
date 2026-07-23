# Fix Test Failures

## Purpose

Systematically triage and fix test failures by identifying root causes, grouping cascading
failures, and resolving issues in dependency order. This skill prevents the common
anti-pattern of fixing failures one-by-one when many share a single root cause.

The lesson this encodes: a single routing/config bug can produce 1000+ test failures;
fixing the root cause resolves most of them instantly. Always find the root cause first.

## When to Use

- When the test suite (`.claude/kit.json` `quality_commands.test`) shows more than ~10 failures
- After a refactoring that introduces widespread breakage
- When failures span multiple test files with similar error patterns
- After dependency upgrades that break test infrastructure

## Procedure

### Step 1: Capture Full Failure Output

Run the suite command(s) from `kit.json` `quality_commands.test` and capture output to a
scratch file (respect the container wrapper if the commands include one):

```bash
<quality_commands.test> 2>&1 > /tmp/test-failures.txt
```

Record the summary line (total / failures / errors).

### Step 2: Categorize by Error Signature

Group failures by their **error message pattern**, not by test file. Common generic
categories:

| Error signature | Likely root cause | Priority |
|-----------------|-------------------|----------|
| Assertion on null where a structure was expected | Endpoint/handler returning the wrong response shape entirely | P0 — routing/wiring |
| Expected 200, got 404 | Route not registered, or swallowed by a catch-all | P0 — routing/wiring |
| Expected 200, got 500 | Runtime error in the handler under test | P1 — code |
| "table/relation not found" | Migration not run or schema mismatch | P0 — schema |
| Type errors / undefined property | Code bug — null safety, contract drift | P1 — code |
| Mock/stub setup errors | Test infrastructure issue | P2 — test |
| Strict-mode/deprecation warnings | Cleanup, not breakage | P3 — cleanup |

### Step 3: Identify Root Causes

For each category, determine whether failures cascade from a single root cause:

1. **Count failures per category** — the largest category is likely a cascade
   (`grep -c "<pattern>" /tmp/test-failures.txt` counts fast)
2. **Check if fixing one thing resolves many** — a routing fix resolves all "null response" failures
3. **Look for shared infrastructure** — middleware, global setup, base classes, fixtures

Cascade heuristics:
- 50+ tests failing with the same signature → likely one root cause
- Failures spanning 10+ test files → likely infrastructure, not individual tests
- Error mentions a framework class, not an app class → likely config/routing

### Step 4: Fix in Priority Order

```
P0: Routing/schema/wiring (fix one, resolve hundreds)
  ↓ rerun suite
P1: Code bugs (fix each, resolve 1-5 tests each)
  ↓ rerun suite
P2: Test infrastructure (mocks, fixtures, factories)
  ↓ rerun suite
P3: Cleanup (warnings, style)
```

After each P-level fix: rerun the full suite, record the new failure count, re-categorize
what remains, continue.

### Step 5: Verify Resolution

Run every command in `quality_commands.test` — all must show 0 failures. Then run
`quality_commands.lint` and `.typecheck` to confirm the fixes didn't introduce new debt.

## Report Format

```markdown
## Test Failure Triage Report

### Initial State
- <suite>: N tests, N failures, N errors

### Root Causes Found
#### Root Cause 1: <description>
- Error signature: <pattern>  Tests affected: <count>
- Fix: <what changed>  Files: <list>  Tests resolved: <count>

### Fix Progression
| Step | Fix applied | Failures before | Failures after | Delta |

### Final State
- <suite>: N tests, 0 failures

### Remaining Issues
<anything unresolved and why — append to .memory/ISSUES.md>
```

## Tips

- Never fix individual test assertions before checking whether the code under test is
  reachable at all (route registered? module wired? schema migrated?)
- Run a single failing test with the runner's verbose flag to see the full response/output
- If tests passed before a specific commit, `git bisect` finds the breaking change
- Root causes that trace to environmental quirks belong in `.memory/GOTCHAS.md` so the
  next session doesn't re-derive them
