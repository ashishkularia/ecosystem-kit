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
5b. Append the decision to this change's diary entry **now**, in the same turn
   — the DECISIONS line is the rule, the diary block is the story around it
   (what was considered, what was rejected, what nearly went wrong). Resolve
   the file with `python3 .claude/hooks/docs_contract.py diary-path`. Writing
   it now is the point: a diary reconstructed at session end has already lost
   the reasoning. The pre-commit gate will block the next `git commit` until
   this lands.
6. If it's an always/never rule about code, propose encoding it as a red
   test in the same session (escalation path + watermark pattern:
   `.memory/references/engineering-principles.md`). Mirror pure style rules
   into `.memory/CONVENTIONS.md`.
7. Design decisions (visual direction, typography, color, spacing, layout,
   component idioms) also update `.memory/references/design-direction*` in
   the same session — the repo doc is canonical and moves FIRST; any
   published claude.ai artifact is a mirror, regenerated FROM the repo file
   afterwards, never edited directly.
