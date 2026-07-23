# Planning

## Purpose

Planning bridges discovery and implementation. Its job is to produce a concrete file
manifest with dependency ordering so builders know exactly what to build, in what order,
with tests first. A good plan catches scope and risk issues before a single line of code
is written.

Planning depth must match ceremony level (`.claude/kit.json` `ceremony`) — a bug fix needs
a mental checklist, not a 30-item manifest.

## Feature Breakdown

### Step 1: Identify Affected Layers

Every change spans a subset of the project's layers. The concrete names depend on the
stack (`kit.json` `stack`), but the generic set is:

| Layer | What lives here |
|-------|----------------|
| Data | Schema/migrations, seed data, stored config |
| Domain logic | Services, handlers, jobs, calculations |
| Authorization | Policies, guards, permission checks |
| Interface | Endpoints/routes, components/pages, CLI commands |
| Registration | Route tables, DI wiring, exports, dashboards |
| Tests | One per layer touched |

### Step 2: List Files per Layer, Count Them

| Complexity | Files | Planning depth |
|-----------|-------|----------------|
| Small | 1-5 | Mental checklist |
| Medium | 6-15 | Brief manifest |
| Large | 16-30 | Full manifest with dependency graph |
| Extra large | 30+ | Split into multiple PRs |

## Task Ordering for TDD

Build inside-out; each layer depends on the one below it, and TDD requires the test before
the implementation:

```
Phase 1: Data layer        TEST → IMPL → GREEN → REFACTOR
Phase 2: Domain logic      TEST → IMPL → GREEN → REFACTOR
Phase 3: Authorization +   TEST → IMPL → GREEN → REFACTOR
         interface
Phase 4: Consumer side     types/contracts first, then TEST → IMPL → GREEN
         (frontend/client)
```

Key insight: consumer-side types and mocks can be written from the interface contract
before the provider side is complete — that is what enables parallel builder work.

## File Manifest Template

Use this format for the architect → builder handoff. The `#` column enables dependency
tracking — builders process files in order and know when they're blocked.

```markdown
## File Manifest: <Feature Name>

### CREATE
| # | File | Purpose | Depends on |
|---|------|---------|------------|
| 1 | <data definition file> | Schema | — |
| 2 | <domain logic file> | Business logic | #1 |
| 3 | <authorization file> | Access control | #2 |
| 4 | <interface file> | Endpoint/component | #2, #3 |

### MODIFY
| # | File | Change | Depends on |
|---|------|--------|------------|
| 5 | <registration file> | Wire up #4 | #4 |

### TESTS (test file per source layer — placed per project convention)
| # | File | Tests for |
|---|------|-----------|
| T1 | <data test> | #1 |
| T2 | <logic test> | #2 |
| T3 | <interface test incl. authorization> | #3, #4 |

### Summary
- Files: N source + N tests = N total, N modified
```

## Risk Assessment

Assess before implementation, not during:

| Category | Risk signals | Mitigation |
|----------|-------------|------------|
| Authorization | New action without an access check | Add check + tests for allowed AND denied |
| Data isolation | Multi-user data without ownership scoping | Scope queries + cross-user denial test |
| Schema migration | Modifying tables that already hold data | Additive changes only; test rollback |
| Performance | Large datasets, joins, unbounded lists | Indexes, eager loading, pagination |
| Data integrity | Cascading deletes, orphaned records | Explicit constraints, soft deletes |
| Concurrency | Shared mutable state | Locking or idempotency strategy |
| Scope | "Nice to have" creep | Define out-of-scope explicitly |
| Unknown patterns | No comparable code exists | Extra discovery; flag to conductor |

## Planning Proportionality

| Ceremony (per kit.json) | Planning artifact |
|--------------------------|-------------------|
| express | None — go |
| standard | Brief manifest (files + order) — fits in one message |
| full | Full manifest with dependency graph and risk assessment |
| critical | Full manifest + ADR (→ `.memory/DECISIONS.md`) + risk assessment + rollback plan |

## Anti-Patterns

1. **Planning without discovery** — existing patterns inform the plan, not the reverse
2. **Missing test plan** — if tests aren't in the manifest, they won't get written
3. **Ignoring dependencies** — building the top layer first creates integration pain
4. **Over-planning** — a 30-item manifest for a 3-file fix
5. **Scope creep during planning** — keep "nice to have" out of the manifest

## Related Skills

- `discovery.md` — must happen before planning
- `adaptive-ceremony.md` — ceremony level determines planning depth
- `handoff.md` — the manifest is the core artifact of the architect → builder handoff
