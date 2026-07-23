---
description: List open ISSUES.md entries and work through one interactively
---

Work the issue backlog in `.memory/ISSUES.md`.

1. List open `- [ ]` entries numbered, with age and a one-line effort/risk
   assessment each.
2. Ask which to tackle (or take the pick from the invocation argument).
3. For the chosen issue: investigate current state first — the observation
   may be stale. Propose the fix; get approval if it is destructive or
   touches anything the project profile marks critical (auth, money, user
   data, prod). Then implement per the docs contract.
4. On resolution: mark `- [x] RESOLVED (date) — outcome` (or delete the line
   if the history isn't instructive), update any `.memory/contexts/` doc it
   made stale, add a `.memory/CHANGELOG.md` line, and a `.memory/VERIFY.md`
   entry if the fix isn't yet verifiable.
5. If investigation shows the issue is invalid or stale, close it with a note
   saying why — that's a finding too.
