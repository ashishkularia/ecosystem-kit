---
description: Write or append this change's diary entry in .memory/diary/
---

Write the diary entry for the change you are working on. Under the default
`diary_scope: "branch"`, that is **one file per branch/MR** —
`.memory/diary/YYYY-MM-DD-<branch-slug>.md`, dated when the branch's diary
started and appended to for the branch's whole life, so everything about a
change lives in one place even when it spans days. Resolve the exact path with:

```bash
python3 .claude/hooks/docs_contract.py diary-path
```

Create it from the skeleton below if absent; otherwise **append** a new
`## <HH:MM> — <short label>` block under the existing entry. Never start a
second file for a branch that already has one, and never rewrite earlier
blocks — the point is an accreting record, not a tidy summary.

(Under `diary_scope: "daily"` the same command writes `YYYY-MM-DD.md` instead.)

## Write it as you go, not at the end

This is the part that matters. A diary written at the Stop gate is a
reconstruction; one written at the moment of the decision is a record. Append a
block **when the thing happens**:

- a decision is made or reversed (`/decide` prompts you, and the pre-commit gate
  will ask for it if you skip)
- a discussion changes the plan, or an approach is rejected
- something surprising is discovered — a wrong assumption, a hidden constraint
- work reaches a checkpoint worth resuming from

Short and frequent beats long and final. Three honest paragraphs written across
the day are worth more than a polished essay at the end.

## What goes in a block

1. First person, honest, to the future you who has lost this session's context —
   not a status report for anyone else.
2. **Discussed:** what was actually talked about, including dead ends and
   rejected approaches (the paths future-you would otherwise re-walk).
3. **Decided:** the calls made — each should also have a `.memory/DECISIONS.md`
   line; add any missing via `/decide` first.
4. **Done:** what changed, in its true state — "built, unverified" beats "done".
   Point at CHANGELOG lines rather than repeating them.
5. **Open:** loose ends and the next-session pointer — what you'd want shouted
   at you before touching the keyboard again.

Not every block needs all five. A mid-work block might be two lines of
**Decided** and nothing else; that is correct usage.

Skeleton:

```markdown
# Diary — <branch-name>

Started YYYY-MM-DD · PR #NN (fill in once opened)

## HH:MM — <short label>

Dear diary,

**Discussed:** …

**Decided:** …

**Done:** …

**Open:** …
```
