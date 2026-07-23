---
description: Work through .memory/VERIFY.md entries whose gates can now be checked
---

Work the verification backlog in `.memory/VERIFY.md`.

1. For each open `- [ ]` entry, decide whether its gate is now checkable
   (tests runnable, deploy happened, the time window passed, real data
   arrived, owner env set). Skip honestly what still isn't — note why.
2. For each checkable entry: verify against its stated **accept** criteria —
   run the command, hit the URL, inspect the row, check the trace. Evidence,
   not vibes; re-reading the code is not verification.
3. Confirmed → delete the entry, and add a `.memory/CHANGELOG.md` line if the
   original change never got one. Failed → keep the entry and record what was
   actually observed in `.memory/ISSUES.md`. Surprising behaviour either way
   → `.memory/GOTCHAS.md`.
4. Report a pass/fail/blocked table. Don't auto-fix failures beyond trivial
   ones — propose.
