# 2026-08-30 — chore/percale-profile

## A sixth repo, and the first one installed before its stack

Every previous profile was written against a repo that already existed: mylantite
had Laravel, grade5 had Workers, homelab had YAML. percale has nothing. The kit
went in first, deliberately, so the SDLC exists from commit one instead of being
retrofitted onto code that already has habits.

That inverts the usual question. Normally you describe a repo you can read; here
the honest answer to most fields is "not yet".

## Empty beats invented

`source_patterns` decides what counts as app source, and therefore when the docs
contract fires. With no framework, any pattern would be a guess about files that
do not exist — and a wrong glob is worse than an empty one, because it classifies
the wrong things silently rather than doing nothing visibly.

So it is empty, which has a real cost: **the docs contract does not fire on code
in that repo.** The kit is installed and, for code changes, inert.

That is the same failure shape this engine keeps producing — something
configured, something else deciding whether it applies, the two disagreeing, and
everything reporting fine. The difference is that this one is known in advance,
so it gets written down four times: the profile's `_note`, percale's STATE (as
the thing to know before writing code), its ISSUES (as an open item), and its
CLAUDE.md.

Four places is not redundancy here. Each is where a different person is looking
at the moment it matters — configuring the kit, starting a session, working the
backlog, reading the policy.

## Not registered on purpose

percale is absent from `~/.claude/repo-registry`, so kit-propagate, the PR poller
and weekly-hygiene all skip it. It will drift behind the kit, and that is
recorded as an open issue rather than left to be discovered.

Registering needs a remote first — kit-propagate's whole output is a PR, and
there is nowhere to open one. The owner chose local-only until the business is
discussed, which for an e-commerce repo carrying future payment and customer-data
obligations is the conservative order.
