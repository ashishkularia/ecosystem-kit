---
description: Revalidate .memory/STATE.md against reality and restamp its date
---

Revalidate `.memory/STATE.md` against what actually exists.

1. Read `.claude/kit.json` — its containers and quality commands tell you
   where reality lives for this project (test suite, running services, deploy
   surface). Pull fresh facts: git log since the last-validated date, the file
   tree vs claimed structure, live counts/status wherever the stack is
   checkable (tests, running containers, deployed URLs). If part of the stack
   isn't up yet, say so and validate what is file-level checkable.
2. Diff against every claim in STATE.md — what's live, counts, positions,
   open gates.
3. Rewrite STATE.md with corrected values and restamp the `Last validated:`
   line with today's date (session_boot warns when it goes >7 days stale).
4. Anything that drifted *surprisingly* (a claimed-live feature isn't, a
   thing vanished, counts moved a lot) → `.memory/ISSUES.md` rather than
   silent correction.
5. Log the revalidation in `.memory/DOCS-CHANGELOG.md`.
