# Discovery

## Purpose

Every healthy codebase is built by following its own existing patterns. When you skip
discovery, you risk inventing a new pattern that conflicts with what's already there — and
the reviewer will send it back. Discovery is fast (a few Glob/Grep calls) and saves
significant rework.

The goal: find one good example of each pattern you need, then follow it.

## Where to Look First

Before touching source, load the project's own map:

| Source | What it gives you |
|--------|-------------------|
| `.claude/kit.json` | Stack, source patterns, containers, quality commands |
| `.memory/STATE.md` | What exists, what's in flight, what's known-broken |
| `.memory/CONVENTIONS.md` | Naming, structure, and style rules the project enforces |
| `.memory/GOTCHAS.md` | Traps previous sessions already fell into — don't repeat them |
| `.memory/contexts/` | Domain deep-dives (the `context_attach` hook surfaces these as you touch matching files) |
| `.memory/DECISIONS.md` | Why things are the way they are — don't relitigate settled decisions |
| Repo root `CLAUDE.md` | Durable policy and the project's own directory map |

## How to Discover

### 1. Find a Comparable Example

Before building anything, find the nearest existing example — same domain or a
similarly-scoped feature. If you're building a CRUD module, look at the closest existing
CRUD module, not at the project's most unusual subsystem.

```
Glob for the sibling implementation files (model/handler/component)
Read the core file first — it reveals the full shape everything downstream follows
Glob for its tests — the test file teaches you fixtures, setup, and naming
```

### 2. Trace a Feature End-to-End

When changing an existing feature, trace all its files so you understand the full surface
before editing anything. Layer names depend on the stack (`kit.json` `stack`), but the
trace is always the same motion:

```
data definition → domain logic → interface (routes/endpoints/components) → registration/config → tests
```

Use Glob on the feature's name across the source tree, and Grep for where it is registered
(routes, service containers, module indexes, exports). This takes 30 seconds and prevents
surprises mid-implementation.

### 3. Check Registration & Configuration Files

Some changes require updating registration files (route tables, DI containers, barrel
exports, config maps, dashboards). Grep for how the comparable example registered itself
and include the same files in your plan.

### 4. Live Inspection (when available)

If the project has MCP tools or CLI commands that query live state (database schema, route
lists, running config), prefer them over inferring state from files — they show reality
including anything that drifted. Fall back to reading source when they're unavailable.

## When to Stop Discovering

Discovery should be proportional to the change:

| Change scope | Discovery depth |
|-------------|-----------------|
| Bug fix in one file | Read that file and its test. Done. |
| Add a field | Read the definition, its serialization, and its tests. |
| New CRUD feature | Full end-to-end trace of a comparable feature. |
| Cross-domain change | Trace each affected domain's files. |

Stop when you can answer both: **"What existing pattern am I following?"** and **"Which
files will I touch?"** If you can't answer both, keep discovering. If you can, move to
planning.

## Discovery Checklist

- [ ] Read `kit.json` `always_load` files (STATE, CONVENTIONS, GOTCHAS at minimum)
- [ ] Found a comparable implementation and read it
- [ ] Found comparable tests and read them
- [ ] Found where the comparable feature is registered/wired
- [ ] Checked `.memory/DECISIONS.md` for constraints on this area
- [ ] Can name the pattern being followed and list the files to touch

## Related Skills

- `planning.md` — discovered patterns and files feed the task manifest
- `adaptive-ceremony.md` — discovery results (scope, domain signals) influence ceremony classification
