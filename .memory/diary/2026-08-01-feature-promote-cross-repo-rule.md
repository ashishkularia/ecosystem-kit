# Diary — feature/promote-cross-repo-rule

Started 2026-08-01 · PR # (fill in once opened)

## Session — lowering the promotion bar

Dear diary,

Ashish: "if any process is capable of being used by more than one repo, then
put the idea in kit. also always explore if the process can benefit any other
repo as well."

**Decided, first, not to file it as an idea** even though he opened with
"another idea is". This is a standing rule about how every future session
works, not something speculative waiting for approval — and IDEAS entries are
explicitly never acted on unasked, so filing it there would have parked a
behavioural rule where it does nothing. It went to DECISIONS as an owner rule
and into the places sessions actually read. I could be wrong about that reading
of his intent, so I'm flagging it rather than burying it.

**What made it concrete:** I went looking for where the rule would bite and
found `/retro` step 4 already had a promotion step — with the bar set at
anything "true for EVERY project using the ecosystem kit". That is a *much*
higher bar than what he asked for, and it fails on today's own work: the
self-hosted-runner guidance is relevant to mylantite and meritick, and not at
all to homelab or grade5. Under the existing wording it is not promotable. Under
his rule it plainly is. So this isn't a nuance — the old text would have
actively rejected the thing we spent the afternoon capturing.

That gave me the phrasing worth keeping: **applicability is not universality.**
Gate a kit artifact by relevance at the point of use — a skill that no-ops where
it doesn't apply — never by keeping it out of the kit.

**The justification I care most about** is one I did not have to invent, because
this repo supplied it today: three forked copies of `split_shell_commands`, only
one of which had learned to extract `$(…)`, and the gap let a push through to a
protected branch. That is exactly the end state of "only one repo needs it today"
— the thing gets copied to the second repo, then the third, and then a fix lands
in one of them. Duplication doesn't just risk inconsistency; it changes the
economics of fixing anything, because patching one copy *feels* like the fix.

**Made it operational, not aspirational.** A promotion rule that lives only in
an architecture diagram is noticed passively, which is the same as not at all —
so: `/retro` step 4 and `/idea` step 5 now ask *could a second repo use this?*
as an explicit step with the question written out; both CLAUDE.mds carry it (the
project template too, so all five repos inherit it on the next propagation); and
the §8 loop diagram's decision line changed from "this learning is not
project-specific" to "could a SECOND repo use this?" — the old line describes a
thing you notice, the new one describes a thing you ask.

**Open / honest caveat:** the failure mode of a low bar is kit bloat — every
project-shaped recipe promoted on a speculative "well, maybe grade5 will need
this". I wrote the counterweight into the rule (domain-bound things — schema,
business rules, infrastructure names — stay put) but that boundary is a judgement
call, not a test, and I expect we'll find the line by getting it wrong once.
Worth watching whether the kit's template count starts growing faster than its
usefulness.
