---
description: Record an architectural/product decision in DECISIONS.md with its why
---

Record the decision given in the argument (or extract it from the current
conversation; if genuinely ambiguous which call is meant, ask).

1. Drop the enforcement flag FIRST, so the Stop gate holds the session open
   until the ledger line actually lands:
   `python3 .claude/hooks/docs_contract.py flag decision "<topic>"` (Bash).
2. State the decision back as one crisp rule — what will always or never be
   done from now on.
3. Capture the WHY in one or two lines. A decision line without its reason is
   half-useless a month later; name who called it if not the owner.
4. Check `.memory/DECISIONS.md` for a conflicting earlier entry. If this
   reverses one, the new line says so ("reverses YYYY-MM-DD …") — old entries
   are never edited or deleted.
5. Add the entry at the top of the list:
   `- YYYY-MM-DD — **the decision as a rule** — the why.`
6. If it's an always/never rule about code, propose encoding it as an
   architecture test / lint rule / hook in the same session — prose doesn't
   survive sessions; red tests do. Mirror pure style rules into
   `.memory/CONVENTIONS.md`.
