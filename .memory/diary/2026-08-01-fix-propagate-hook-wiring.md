# Diary — fix/propagate-hook-wiring

Started 2026-08-01 · PR # (fill in once opened)

## Session — the feature that would have shipped as dead code

Dear diary,

Ashish merged PRs #17 and #18 and asked me to check. Everything verified clean
— both commits free of attribution trailers, 136 tests green on merged main, a
fresh install scoring 90% with the commit gate firing correctly end to end.

Then I checked the thing that actually matters: whether his *existing* repos
would get the feature. They would not have.

**The gap.** `update.sh` ships engine FILES but never rewrites
`settings.json`, and that rule is correct — settings.json is project-owned, and
homeassistant genuinely wires a project-local `guard_lint_md` in there that a
template overwrite would delete. But the pre-commit diary gate is not a new
*module*; it is an existing module (`docs_contract`) wired onto a NEW event
(`PreToolUse|Bash`). The wiring lives in `settings.json.template`, which
existing repos never receive. So all five installed repos would have taken the
new `docs_contract.py` and never called the new code path. The feature would
have been present, tested, documented, and dead.

Worse, it would have been *silently* dead. `health-check`'s wiring check
compares the settings roster against the hooks glob, and `docs_contract` is
still wired (on PostToolUse and Stop) — so the check passes. Nothing anywhere
would have said "the gate you just shipped is not connected."

**Decided:** fix it as a kit-propagate **policy patch**, not by relaxing
update.sh. That mechanism already exists for precisely this class of thing —
`patch_attribution` merges the attribution block into settings.json because
update.sh won't. Hook wiring is the same shape of problem: a kit-wide rule that
lives in a project-owned file. Following the existing pattern beat inventing a
new one, and it keeps update.sh's never-touch guarantee intact.

The patch is **strictly additive**: it appends a (event, matcher, hook) triple
only when the template has it and the target does not. Never removes, never
reorders, never touches a matcher group the template doesn't define. Verified
against homeassistant's real settings.json — `docs_contract` was added,
`guard_lint_md` survived, pre-existing ordering preserved byte for byte,
non-hook keys untouched, and a second run is a no-op.

**Rejected:** having update.sh merge the template wiring directly. It would
work, but it turns "update.sh never touches settings.json" into "update.sh
sometimes touches settings.json", and that guarantee is why the file is safe to
customize. A hard rule with an exception is a soft rule.

**Open:** kit-propagate runs from `~/.claude/bin/`, so this needs redeploying
there after merge (`tools/bootstrap-machine.sh`) — otherwise tomorrow's 06:37
run uses the old copy and the five PRs it opens still won't carry the wiring.
Flagged in the PR.

**The lesson worth keeping:** "the tests pass and the feature works" was true
and irrelevant. It worked in a *fresh install*, which is the one configuration
none of the real repos are in. Shipping to an installed base means verifying
the upgrade path, not the install path — and the kit's whole reason for
existing is the installed base.
