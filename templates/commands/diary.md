---
description: Write or append today's diary entry in .memory/diary/
---

Write today's diary entry: `.memory/diary/YYYY-MM-DD.md`. Create it from the
skeleton below if absent; if it already has a session block from earlier
today, append a new `## Session — <label>` block below it. The Stop gate
(docs_contract, when `kit.json` `diary` is true) checks today's file was
touched before the session ends — this command writes it properly.

1. Look back over the session honestly, first person — this is the
   note-to-future-self that survives context loss, not a status report.
2. **Discussed:** what we actually talked about, including dead ends and
   rejected approaches (those are the paths future-me would otherwise
   re-walk).
3. **Decided:** the calls made — each should have a `.memory/DECISIONS.md`
   line; add any missing via /decide first.
4. **Done:** what shipped or changed, in its true state — "built, unverified"
   beats "done". Point at CHANGELOG lines rather than repeating them.
5. **Open:** loose ends and the next-session pointer — what I'd want shouted
   at me tomorrow morning before touching the keyboard.

Skeleton (one `## Session` block per session; multi-session days append the
next block below the previous one):

```markdown
# Diary — YYYY-MM-DD

## Session — <short label>

Dear diary,

**Discussed:** …

**Decided:** …

**Done:** …

**Open:** …
```
