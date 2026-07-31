---
description: Distill the session into durable memory; propose kit promotions
---

Run a session retrospective. The goal: nothing learned today gets re-learned
next month.

1. Review the whole session — user corrections, surprises, decisions made,
   recipes that worked, style preferences expressed or implied.
2. Route each finding to its durable home:
   - Corrected wrong assumption about the system → `.memory/GOTCHAS.md`
   - Owner "always/never do X here" → `.memory/CONVENTIONS.md` (encode per
     the escalation path in `.memory/references/engineering-principles.md`)
   - A call with a why → `.memory/DECISIONS.md` (via the /decide format)
   - A multi-step recipe worth repeating → `.memory/references/<topic>.md`
   - Personal style / cross-project workflow preference → auto-memory
3. Cross-check the documentation contract: CHANGELOG, DOCS-CHANGELOG, VERIFY,
   ISSUES all carry what this session owes them. File anything missing now.
4. Propose **kit promotions**: anything learned here that is true for EVERY
   project using the ecosystem kit (a hook gap, a better command body, a
   template fix) — list each explicitly so the owner can carry it to the
   ecosystem-kit repo. Do not edit the kit from a project session.
5. Append a closing block to this change's diary entry (/diary) if the session's
   work is not already recorded there.
