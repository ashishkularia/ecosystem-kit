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
4. Propose **kit promotions**. The bar is **a second EXISTING repo, today** —
   more than one repo, not every repo (owner rule 2026-08-01). Ask it actively,
   as its own step, not as something you notice in passing:

   > For each process, recipe, guard, script or runbook this session built or
   > fixed — **which existing repo could implement this right now, or already
   > has its own version of it?** Name it. What would need changing to make it
   > reusable there?

   **If you cannot name a repo, it is not a promotion — leave it here.** A
   future need is not a reason: if another repo might want this later, promote
   it when that repo actually needs it. Nothing is lost by waiting; it is the
   same work done with evidence instead of a guess, and it keeps the kit from
   filling with artifacts nobody uses.

   If you *can* name one, list the promotion explicitly so the owner can carry
   it to the ecosystem-kit repo. **Another repo already having its own version
   is the strongest case — that means the promotion is overdue, not early.**
   Applicability is not universality: something serving two of five repos still
   belongs in the kit, gated by relevance at use time rather than excluded.

   Genuinely project-bound things stay put: this repo's schema, business
   rules, infrastructure names. Do not edit the kit from a project session.
5. Append a closing block to this change's diary entry (/diary) if the session's
   work is not already recorded there.
