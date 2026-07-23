# .memory/contexts/ — task briefings

A context doc is the briefing you'd give a competent new team member before
they touch ONE area of this project: the facts they can't guess, the rules
that aren't negotiable, and the traps that already bit someone. It is a
read-first document, not a reference manual — one screen of load-bearing
content beats ten screens of completeness.

## Naming and wiring

- One file per work area, named `<area>-work.md` — `ui-work.md`,
  `marking-work.md`, `ops-work.md`, `content-work.md`.
- Wire each doc into `domain_map` in `.claude/kit.json` with a file-pattern
  regex. The `context_attach` hook then auto-surfaces it (once per session)
  the moment a matching file is read or edited. **An unwired context doc is
  never auto-surfaced** — wiring is part of creating it.

## Skeleton that works

```markdown
# <Area> work — read before touching <paths>

## Read first
Links to the references/ docs and external material this work leans on.

## Facts
The non-guessable ground truth: which classes/entities/services are involved,
where the data lives, what the pipeline looks like. Numbers and names, not
prose.

## Rules
The always/never list for this area, each with its one-line why. If a rule is
enforceable, it should ALSO exist as a test/hook — say where.

## Pitfalls
The traps specific to this area (general ones live in GOTCHAS.md — link,
don't duplicate).

## Definition of done
What "finished" means here beyond green tests: docs updated, verified in both
themes, eval run recorded — whatever this area demands.
```

## Staleness contract

A change that makes a context doc wrong updates it **in the same session** —
the docs-contract hook reminds, and the DOCS-CHANGELOG gets a line. A stale
briefing is worse than none: the next session will trust it.
