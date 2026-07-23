---
description: Discuss and flesh out a new idea, then record it in IDEAS.md
---

Capture and develop the idea given in the argument (or ask for it).

1. Drop the enforcement flag FIRST, so the Stop gate holds the session open
   until the discussion reaches the diary:
   `python3 .claude/hooks/docs_contract.py flag discussion "<topic>"` (Bash).
2. Interrogate it briefly: what problem does it solve, which part of the
   system does it touch, what's the smallest useful version?
3. Check it against reality: is it already in scope, explicitly cut, or
   genuinely new? Does it conflict with a `.memory/DECISIONS.md` entry or a
   non-negotiable in CLAUDE.md? Do its prerequisites exist yet? Note blockers
   honestly.
4. Discuss trade-offs until the idea has a crisp shape.
5. Record in `.memory/IDEAS.md`: bold title, 2–4 lines covering the what, the
   approach, and any prerequisite. Datestamp if time-sensitive.
6. Do NOT implement it — IDEAS.md entries are acted on only when explicitly
   asked.
