---
description: Discuss and flesh out a new idea, then record it in IDEAS.md
---

Capture and develop the idea given in the argument (or ask for it).

1. Drop the enforcement flag FIRST, so the gates hold the session open until
   the discussion reaches the diary:
   `python3 .claude/hooks/docs_contract.py flag discussion "<topic>"` (Bash).
   Append the discussion to this change's diary entry as it develops — dead
   ends and rejected shapes especially, since those are what future-you would
   otherwise re-walk. The next `git commit` blocks until it lands.
2. Interrogate it briefly: what problem does it solve, which part of the
   system does it touch, what's the smallest useful version?
3. Check it against reality: is it already in scope, explicitly cut, or
   genuinely new? Does it conflict with a `.memory/DECISIONS.md` entry or a
   non-negotiable in CLAUDE.md? Do its prerequisites exist yet? Note blockers
   honestly.
4. Discuss trade-offs until the idea has a crisp shape.
5. **Ask where it belongs before writing it down** (owner rule 2026-08-01):
   *which existing repo could implement this right now, or already has its own
   version?* If you can name one — even a single other repo, not all of them —
   it is a kit idea, not a project idea, and the entry says so and names the
   repo. If you cannot name one, it stays a project idea: a future need is not
   a reason, and when that repo actually needs it the promotion happens then.
   Applicability is not universality — something serving two of five repos
   still belongs in the kit, gated by relevance at use time. Filing a process
   another repo is *already* doing as project-local is how three copies come to
   exist and then drift apart.
6. Record in `.memory/IDEAS.md`: bold title, 2–4 lines covering the what, the
   approach, and any prerequisite. Datestamp if time-sensitive.
7. Do NOT implement it — IDEAS.md entries are acted on only when explicitly
   asked.
