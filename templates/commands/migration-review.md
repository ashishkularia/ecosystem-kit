# /migration-review - Database Migration Safety Review

## Description
Reviews database migrations against the migration safety checklist, checking for reversibility, data safety, per-user isolation, UUID consistency, and deployment readiness.

## Usage
```
/migration-review [migration-file-or-directory]
```

**Target:** $ARGUMENTS

- No argument: Reviews all pending/recent migrations in `database/migrations/`
- File path: Reviews a specific migration file
- Directory: Reviews all migration files in the directory

## Process

### Step 1: Load Checklist
Use the Read tool to load the migration safety checklist before proceeding:
- `.claude/agents/devops-guardian.md` (Section 3: Database Migration Safety Review)
- `.memory/contexts/implementation-checklist.md` (Database Migrations section)

### Step 2: Identify Migrations
1. If `$ARGUMENTS` specifies a file, read that file
2. If `$ARGUMENTS` specifies a directory, glob for `*.php` migration files
3. If no argument, find recently modified migrations:
   ```bash
   # Find migrations modified in the last 7 days
   find database/migrations -name "*.php" -mtime -7
   ```
4. Read each identified migration file

### Step 3: Execute All 10 Checklist Sections

For each migration file, verify every item in all 10 sections:

1. **Reversibility** — Verify `down()` exists and reverses all `up()` operations
2. **Data Safety** — Check for destructive operations (DROP, TRUNCATE, type narrowing)
3. **Lock Risk & Performance** — Estimate lock impact on large tables
4. **Foreign Key Ordering** — Verify parent-before-child in `up()`, child-before-parent in `down()`
5. **Per-User FK** — Verify `user_id` presence and index on user-owned tables
6. **UUID Consistency** — Verify `uuid('id')->primary()` and `foreignUuid()` usage
7. **Soft Deletes** — Verify `softDeletes()`, and that uniqueness on a soft-delete
   table is a PARTIAL unique index (`… WHERE deleted_at IS NULL`), not
   `unique([col, 'deleted_at'])`
8. **Index Strategy** — Verify indexes match expected query patterns
9. **Concurrent Execution** — Verify zero-downtime safety
10. **Rollback Testing** — Run the rollback cycle test

### Step 4: Run Rollback Test
Run the migrate → rollback → migrate cycle. Take the container from
`.claude/kit.json` `containers.app` and run it there; if `containers` is empty,
this project runs on the host and the commands run directly.

```bash
# containerized (containers.app set):
docker exec <containers.app> bash -c '
  <migrate> 2>&1 && <rollback one step> 2>&1 && <migrate> 2>&1 && \
  echo "ROLLBACK TEST: PASS" || echo "ROLLBACK TEST: FAIL"
'
```

The migrate/rollback verbs are stack-specific — Laravel is
`php artisan migrate` / `php artisan migrate:rollback --step=1`; use whatever
`kit.json` `quality_commands` and the project's own docs establish for this
stack. A migration that cannot be rolled back is a FAIL regardless of stack.

### Step 5: Generate Report

```markdown
## Migration Safety Report
Date: [date]
Reviewer: migration-review
Migration(s): [file list]

### Summary
| Section | Status | Issues |
|---------|--------|--------|
| 1. Reversibility | PASS/WARN/FAIL | [count] |
| 2. Data Safety | PASS/WARN/FAIL | [count] |
| 3. Lock Risk & Performance | PASS/WARN/FAIL | [count] |
| 4. Foreign Key Ordering | PASS/WARN/FAIL | [count] |
| 5. Per-User FK | PASS/WARN/FAIL | [count] |
| 6. UUID Consistency | PASS/WARN/FAIL | [count] |
| 7. Soft Deletes | PASS/WARN/FAIL | [count] |
| 8. Index Strategy | PASS/WARN/FAIL | [count] |
| 9. Concurrent Execution | PASS/WARN/FAIL | [count] |
| 10. Rollback Testing | PASS/WARN/FAIL | [count] |

### Auto-Fail Conditions Triggered
[List — these block merge]

### Warnings
[List — require justification]

### Detailed Findings
[Per-section with file:line references]

### RESULT: PASS / FAIL
```

## Auto-Fail Conditions

These conditions cause an automatic FAIL result:

1. Empty `down()` method without documented justification
2. `DROP COLUMN` or `DROP TABLE` without data migration plan
3. `foreignId()` used instead of `foreignUuid()`
4. `$table->id()`, `$table->increments()`, or `$table->bigIncrements()` used
5. User-owned table missing `user_id` FK column
6. `user_id` FK without an index on user-owned table
7. Rollback cycle fails at any step

## Common Warnings

These do not block merge but require documented justification:

1. Uniqueness on a soft-delete table written as `unique([col, 'deleted_at'])` —
   this is a BLOCKER, not a warning: it enforces nothing (NULLs are DISTINCT in
   a unique index). Use a partial unique index.
2. ALTER on high-traffic table (`users`, `practice_tests`, `questions`, `test_attempts`)
3. `nullable()` to `NOT NULL` without default or backfill
4. More than 5 indexes on a single table
5. `cascadeOnDelete()` where both sides use soft deletes
6. Migration estimated >30 seconds on production data
7. `$table->enum(` — forbidden; use `varchar` + an Eloquent enum cast
