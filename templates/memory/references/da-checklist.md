# Devil's Advocate Checklist

The consolidated DA checklist — four dimensions: architecture, security, performance,
reliability. Used by the reviewer during DA analysis (process and scoring in
`.claude/skills/devils-advocate.md`; which dimensions apply at each ceremony level is
defined there, gates per `.claude/kit.json`).

**How to use**: for each check, ask the question and judge PASS/FAIL. Every FAIL at
Critical or High severity must block the merge. Add project-specific examples to this file
over time — it lives in `.memory/` precisely so it can accumulate project knowledge.

---

## Dimension 1: Architecture

### A1. Over-Engineering (YAGNI)
**Question**: Is any abstraction, option, or layer present without a current, concrete need?
- PASS: every abstraction has ≥2 real consumers or a stated, imminent second use
- FAIL: interfaces with one implementation, speculative config, pass-through layers
- Risk: **Medium**

### A2. Coupling
**Question**: Do modules reach into each other's internals, or communicate through declared interfaces?
- PASS: cross-module use goes through public exports/contracts; no circular imports
- FAIL: deep imports into another module's internals; shared mutable state across modules
- Risk: **Medium**

### A3. Pattern Consistency
**Question**: Does the change follow the nearest comparable existing pattern?
- PASS: a comparable was identified (discovery) and mirrored, or the deviation has a recorded decision
- FAIL: a new parallel pattern for a problem the codebase already solves
- Risk: **Medium**

### A4. Scalability
**Question**: Does the design survive 10x the data/traffic it sees today?
- PASS: bounded queries, pagination, no per-item remote calls in loops, queue-able heavy work
- FAIL: loads whole tables into memory, fan-out that grows with data size, synchronous heavy work in request path
- Risk: **High**

### A5. Reversibility
**Question**: Can this change be rolled back without data loss or manual surgery?
- PASS: migrations reversible (or explicitly, deliberately not), feature isolated behind its interface
- FAIL: destructive migration with an empty rollback; change entangles unrelated modules
- Risk: **High**

## Dimension 2: Security

### S1. Authorization on Every Action
**Question**: Does every state-changing or data-revealing action check that the caller is allowed?
- PASS: every endpoint/handler enforces an authorization check; both allow and deny paths tested
- FAIL: any action reachable without a check; only the happy role tested
- Risk: **Critical**

### S2. Ownership / Tenant Isolation
**Question**: Where data belongs to a user/tenant, can one caller ever touch another's data?
- PASS: lookups scoped to the owner; lists/search filtered by owner; cross-owner access tested and denied; batch operations verify ownership of every ID
- FAIL: unscoped lookups by ID; list endpoints returning all rows; no cross-owner test
- Risk: **Critical**

### S3. Input Validation at the Boundary
**Question**: Is every piece of external input validated before use — including nested structures, files, and enum values?
- PASS: allowlist validation, length/size limits, nested fields validated, uploads checked by type AND content
- FAIL: raw request data passed through; unbounded strings; unvalidated nested arrays
- Risk: **High**

### S4. Injection Prevention
**Question**: Can external input ever reach an interpreter (SQL, shell, HTML/DOM, template) unescaped?
- PASS: parameterized queries only; no string-built shell commands; output escaped by default; dynamic identifiers (column/sort names) validated against an allowlist
- FAIL: string interpolation into SQL/shell; raw HTML from user content; `orderBy(userInput)`
- Risk: **Critical**

### S5. Mass Assignment / Privileged Fields
**Question**: Can a caller set fields they shouldn't (owner IDs, roles, scores, balances) via the write path?
- PASS: privileged fields set server-side only; explicit allowlists on writable fields
- FAIL: owner/role/score fields writable from the request payload
- Risk: **Critical**

### S6. Secrets & Sensitive Data
**Question**: Are secrets out of code/config-in-repo, and sensitive fields out of responses and logs?
- PASS: secrets only in env; responses use explicit serializers that omit internal/sensitive fields; no PII/tokens in logs
- FAIL: hardcoded keys; raw model dumps in responses; internal IDs/soft-delete markers leaked
- Risk: **Critical** (secrets) / **High** (exposure)

### S7. Auth Session Hygiene
**Question**: Are tokens stored and rotated safely, and are auth endpoints rate-limited?
- PASS: tokens out of script-readable storage; credential change invalidates sessions; login rate-limited
- FAIL: tokens in localStorage-equivalent; no rate limits; eternal refresh tokens
- Risk: **Critical**

### S8. Third-Party Boundaries
**Question**: Are callbacks and webhooks verified, and external responses validated?
- PASS: webhook signatures verified; OAuth state validated; redirect targets allowlisted; external data validated before trust
- FAIL: unauthenticated webhooks; open redirects; blind trust of external payloads
- Risk: **High**

### S9. Audit Trail
**Question**: Are security-relevant events (auth, permission changes, sensitive access) logged with actor attribution?
- PASS: actor + action + target + timestamp on security events
- FAIL: silent permission changes; logs without actors
- Risk: **High**

## Dimension 3: Performance

### P1. N+1 Access Patterns
**Question**: Does any loop perform a query/remote call per item?
- PASS: related data eager-loaded or batched
- FAIL: per-row queries, per-item HTTP calls
- Risk: **High**

### P2. Indexes Match Queries
**Question**: Is every filtered/sorted/joined column covered by an index?
- PASS: new query patterns come with matching indexes; no gratuitous index sprawl either
- FAIL: full scans on growing tables; filter columns unindexed
- Risk: **Medium** (High on hot paths)

### P3. Bounded Data
**Question**: Is every list paginated and every payload size capped?
- PASS: pagination with a max page size; queries select what they need
- FAIL: unbounded lists; client-controlled `per_page` with no cap; `SELECT *` on wide hot tables
- Risk: **High**

### P4. Payload & Bundle Impact
**Question**: Does the change bloat what ships to the client (bundle, response size, assets)?
- PASS: heavy components lazy-loaded; dependencies weighed before adoption; responses lean
- FAIL: large dependency added for one function; everything eagerly loaded
- Risk: **Medium**

### P5. Hot-Path Discipline
**Question**: Does the change add work to the project's known hot paths?
- PASS: hot paths measured before/after, or untouched; caching considered with an invalidation story
- FAIL: synchronous extra calls added to the critical path unmeasured
- Risk: **High**

## Dimension 4: Reliability

### R1. Race Conditions
**Question**: Can concurrent callers corrupt shared state (double-submit, double-spend, duplicate creation)?
- PASS: uniqueness enforced at the storage layer; locking or idempotency where state transitions matter
- FAIL: check-then-act without a lock; client-side-only duplicate prevention
- Risk: **Critical** on money/state machines, else **High**

### R2. Error Handling Gaps
**Question**: What happens when the dependency fails, the input is malformed, the timeout fires?
- PASS: failures surface fast with context (see fail-fast principle); retries only where idempotent; user sees an honest error state
- FAIL: swallowed exceptions; infinite/blind retries; success UI on failed writes
- Risk: **High**

### R3. Data Consistency
**Question**: Can a partial failure leave data half-written?
- PASS: multi-step writes transactional or compensated; FK/constraint integrity preserved; orphan cleanup exists
- FAIL: multi-table writes without a transaction; cascades that silently destroy or silently orphan
- Risk: **Critical**

### R4. Crash / Restart Recovery
**Question**: If the process dies mid-operation, does the system recover cleanly?
- PASS: jobs idempotent and resumable; in-flight state detectable and reconcilable
- FAIL: jobs that double-apply on retry; state only in memory
- Risk: **High**

### R5. Time & Boundary Edges
**Question**: Are the edges handled — empty, null, zero, max, expiry-instant, timezone/DST?
- PASS: boundary tests exist (off-by-one, exactly-at-limit, empty set); server is the time authority
- FAIL: client-supplied timestamps trusted; limits tested only away from the boundary
- Risk: **Medium** (High where money/scoring/deadlines are involved)

---

## Severity Classification

| Severity | Definition | Action required |
|----------|-----------|-----------------|
| Critical | Exploitable vulnerability, data loss, isolation breach, privilege escalation | Fix before merge. No exceptions. |
| High | Significant weakness exploitable/hit with moderate effort | Fix, or document accepted risk with a mitigation timeline in `.memory/ISSUES.md` |
| Medium | Reduces defense-in-depth or violates best practice | Should fix; may defer with documented justification |
| Low | Minor improvement or hardening opportunity | Nice to fix; deferral fine |

## Project-Specific Priorities

Append the project's own ranked priorities here as they become clear (which data is most
sensitive, which paths are business-critical, which failures are most expensive). These
priorities calibrate severity when a check could plausibly score at two levels.
